# -------------------- 请用这个最终的、与 gnpy==2.12.1 兼容的完整文件内容替换 --------------------

import math
import traceback
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorDatabase
from ..crud import crud_network
from ..models.simulation import SingleLinkSimulationRequest, SingleLinkSimulationResponse, SimulationStepResult
from .gnpy_adapter import convert_to_gnpy_json

# --- GNPy Imports (Corrected and Verified for version 2.12.1) ---
from gnpy.tools.json_io import load_equipment, network_from_json
from gnpy.core.network import build_network
from gnpy.core.info import create_input_spectral_information
from gnpy.core.utils import lin2db


class SimulationError(Exception):
    def __init__(self, message, status_code=400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


EQPT_CONFIG_PATH = Path(__file__).parent.parent.parent / "eqpt_config.json"


async def simulate_single_link_gnpy(db: AsyncIOMotorDatabase,
                                    request: SingleLinkSimulationRequest) -> SingleLinkSimulationResponse:
    """
    Performs an optical transmission simulation using the GNPy library version 2.12.1.
    """
    network_model = await crud_network.get_network(db, request.network_id)
    if not network_model:
        raise SimulationError(f"Network with id {request.network_id} not found.", status_code=404)

    gnpy_network_json = convert_to_gnpy_json(network_model, request.path)

    try:
        equipment = load_equipment(str(EQPT_CONFIG_PATH))
        network = network_from_json(gnpy_network_json, equipment)
        build_network(network, equipment, 0, 0)

        si_config = equipment['SI']['default']
        initial_spectral_info = create_input_spectral_information(
            f_min=si_config.f_min, f_max=si_config.f_max, spacing=si_config.spacing,
             baud_rate=si_config.baud_rate, roll_off=si_config.roll_off,
            tx_osnr=si_config.tx_osnr, tx_power=request.input_power_dbm
        )

        # --- 核心修复 #1: 获取路径上真实的 "元素对象" 列表 ---
        # We need to get the actual node objects from the network graph in the correct order.
        node_map = {n.uid: n for n in network.nodes()}
        path_elements = []
        for uid in request.path:
            element = node_map.get(uid)
            if element is None:
                raise SimulationError(f"Element with UID '{uid}' from path not found in the network.", status_code=404)
            path_elements.append(element)

        path_results = []
        # The spectral_info object will be mutated by each element's propagate method
        spectral_info = initial_spectral_info.copy()
        channel_index = 0  # Assuming we are interested in the first channel

        # --- 核心修复 #2: 遍历元素并调用每个元素的 .propagate() 方法 ---
        for element in path_elements:
            # Capture state *before* propagation (input to the element)
            si_in = spectral_info.copy()

            # The .propagate method modifies the spectral_info object in-place
            element.propagate(spectral_info)

            # Now, spectral_info represents the state *after* propagation (output of the element)
            si_out = spectral_info

            # Extract metrics from spectral info before and after
            input_power_watts = si_in.signal[channel_index]
            output_power_watts = si_out.signal[channel_index]
            input_ase_watts = si_in.ase[channel_index]
            output_ase_watts = si_out.ase[channel_index]
            input_nli_watts = si_in.nli[channel_index]
            output_nli_watts = si_out.nli[channel_index]

            input_power_dbm = 10 * math.log10(input_power_watts * 1000)
            output_power_dbm = 10 * math.log10(output_power_watts * 1000)

            input_total_noise = input_ase_watts + input_nli_watts
            output_total_noise = output_ase_watts + output_nli_watts

            input_osnr_db = lin2db(input_power_watts / input_total_noise) if input_total_noise > 0 else float('inf')
            output_osnr_db = lin2db(output_power_watts / output_total_noise) if output_total_noise > 0 else float('inf')

            added_noise_mw = (output_total_noise - input_total_noise) * 1000

            path_results.append(SimulationStepResult(
                element_id=element.uid,
                element_type=type(element).__name__,
                input_power_dbm=round(input_power_dbm, 2),
                input_osnr_db=round(input_osnr_db, 2) if input_osnr_db != float('inf') else None,
                output_power_dbm=round(output_power_dbm, 2),
                output_osnr_db=round(output_osnr_db, 2) if output_osnr_db != float('inf') else None,
                added_noise_mw=added_noise_mw,
                details={"latency_ms": element.latency * 1000 if hasattr(element, 'latency') else 0}
            ))

        if not path_results:
            raise SimulationError("Simulation failed to produce results. Check path and element parameters.",
                                  status_code=500)

        return SingleLinkSimulationResponse(
            path_results=path_results,
            final_osnr_db=path_results[-1].output_osnr_db,
            final_power_dbm=path_results[-1].output_power_dbm
        )

    except Exception as e:
        print("--- An exception occurred in GNPy simulation service ---")
        traceback.print_exc()
        print("---------------------------------------------------------")
        raise SimulationError(f"GNPy simulation engine error: {str(e)}", status_code=500)

