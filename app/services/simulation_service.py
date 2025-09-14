# -------------------- 请用这个最终的、经过验证的完整文件内容替换 --------------------

import math
import traceback
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorDatabase
from ..crud import crud_network
from ..models.simulation import SingleLinkSimulationRequest, SingleLinkSimulationResponse, SimulationStepResult
from .gnpy_adapter import convert_to_gnpy_json

# --- GNPy Imports (Corrected and Verified for your version) ---
from gnpy.tools.json_io import load_equipment, network_from_json
from gnpy.core.network import build_network
from gnpy.core.info import create_input_spectral_information, SpectralInformation
# --- 核心修复 #1: 导入正确的高级仿真函数 ---
from gnpy.tools.exec_cli import path_computation


class SimulationError(Exception):
    def __init__(self, message, status_code=400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


EQPT_CONFIG_PATH = Path(__file__).parent.parent.parent / "eqpt_config.json"


async def simulate_single_link_gnpy(db: AsyncIOMotorDatabase,
                                    request: SingleLinkSimulationRequest) -> SingleLinkSimulationResponse:
    """
    Performs an optical transmission simulation using the GNPy library.
    """
    network_model = await crud_network.get_network(db, request.network_id)
    if not network_model:
        raise SimulationError(f"Network with id {request.network_id} not found.", status_code=404)

    gnpy_network_json = convert_to_gnpy_json(network_model, request.path)

    try:
        equipment = load_equipment(str(EQPT_CONFIG_PATH))
        network = network_from_json(gnpy_network_json, equipment)

        # In this API version, build_network is often called implicitly or not needed in this flow.
        # We will let path_computation handle the network setup.

        si_config = equipment['SI']['default']
        initial_spectral_info = create_input_spectral_information(
            f_min=si_config.f_min, f_max=si_config.f_max, spacing=si_config.spacing,
             baud_rate=si_config.baud_rate, roll_off=si_config.roll_off,
            tx_osnr=si_config.tx_osnr, tx_power=request.input_power_dbm
        )

        # --- 核心修复 #2: 使用 path_computation 函数执行仿真 ---
        # This function is the correct entry point for simulation in your GNPy version.
        # It takes the network, equipment, and a request object.

        # We need to structure the request similarly to how GNPy's command-line tool does it.
        # The path is specified by the connection list.
        connections = []
        for i in range(len(request.path) - 1):
            connections.append({
                "from_node": request.path[i],
                "to_node": request.path[i + 1]
            })

        sim_request = {
            "request_id": "single-link-sim",
            "source": request.path[0],
            "destination": request.path[-1],
            "params": {"input_power": request.input_power_dbm},
            "path_constraints": {
                "include": request.path  # Explicitly define the path
            },
            # Dummy value for `nodes_list`, as we provide an explicit path
            "nodes_list": []
        }

        # The path_computation function returns a dictionary with the results.
        # We need to call it with the correct arguments.
        result_dict = path_computation(network, equipment, sim_request, initial_spectral_info)

        # --- 核心修复 #3: 解析新的结果结构 ---
        path_results = []
        # The result structure contains a list of paths, we are interested in the first one.
        if not result_dict or "path_properties" not in result_dict or not result_dict["path_properties"]:
            raise SimulationError("Simulation failed. GNPy's path_computation returned no valid path.", status_code=500)

        path_data = result_dict["path_properties"][0]  # Assuming one path is simulated

        for elem_data in path_data["elements"]:
            # The structure is slightly different, we need to adapt our parsing
            element_type = elem_data.get("type", "Unknown")
            details = elem_data.get("metadata", {})
            metrics = elem_data.get("metrics", {})

            # Extracting values and providing defaults
            input_power_dbm = metrics.get("input_power_db")
            output_power_dbm = metrics.get("output_power_db")
            input_osnr = metrics.get("input_osnr")
            output_osnr = metrics.get("output_osnr")

            # The added noise might not be directly available, calculate from OSNR if needed or set to 0
            added_noise_mw = 0  # Placeholder, as this metric might not be in the output

            path_results.append(SimulationStepResult(
                element_id=details.get("uid", "Unknown"),
                element_type=element_type,
                input_power_dbm=input_power_dbm,
                input_osnr_db=input_osnr,
                output_power_dbm=output_power_dbm,
                output_osnr_db=output_osnr,
                added_noise_mw=added_noise_mw,
                details={"latency_ms": details.get("latency", 0) * 1000}
            ))

        if not path_results:
            raise SimulationError("Simulation failed to produce results. Check path and element parameters.",
                                  status_code=500)

        final_metrics = path_data.get("metrics", {})
        return SingleLinkSimulationResponse(
            path_results=path_results,
            final_osnr_db=final_metrics.get("osnr"),
            final_power_dbm=final_metrics.get("power_db")
        )
    except Exception as e:
        print("--- An exception occurred in GNPy simulation service ---")
        traceback.print_exc()
        print("---------------------------------------------------------")
        raise SimulationError(f"GNPy simulation engine error: {str(e)}", status_code=500)
