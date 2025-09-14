# -------------------- 这是带有诊断功能的最终调试文件 --------------------

import math
import traceback
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorDatabase
from ..crud import crud_network
from ..models.simulation import SingleLinkSimulationRequest, SingleLinkSimulationResponse, SimulationStepResult
from .gnpy_adapter import convert_to_gnpy_json

from gnpy.tools.json_io import load_equipment, network_from_json
from gnpy.core.network import build_network
from gnpy.core.info import create_input_spectral_information
from gnpy.core.elements import Transceiver
from gnpy.core.utils import lin2db


class SimulationError(Exception):
    def __init__(self, message, status_code=400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


EQPT_CONFIG_PATH = Path(__file__).parent.parent.parent / "equipment.json"


async def simulate_single_link_gnpy(db: AsyncIOMotorDatabase,
                                    request: SingleLinkSimulationRequest) -> SingleLinkSimulationResponse:
    network_model = await crud_network.get_network(db, request.network_id)
    if not network_model:
        raise SimulationError(f"Network with id {request.network_id} not found.", status_code=44)

    gnpy_network_json = convert_to_gnpy_json(network_model, request.path)

    try:
        equipment = load_equipment(str(EQPT_CONFIG_PATH))

        network = network_from_json(gnpy_network_json, equipment)
        build_network(network, equipment, 0, 0)

        si_config = equipment['SI']['default']

        # --- !! 关键的诊断代码 !! ---
        print("

              - -- DEBUGGING
        si_config
        OBJECT - --")
        print(f"Type of si_config: {type(si_config)}")
        print(f"Content of si_config: {si_config}")
        print(f"All attributes of si_config: {dir(si_config)}")
        print("------------------------------------

              ")
        # --- 诊断代码结束 ---

        spectral_info = create_input_spectral_information(
            f_min=si_config.f_min,
            f_max=si_config.f_min + (si_config.n_ch - 1) * si_config.spacing,
            spacing=si_config.spacing,
            baud_rate=si_config.baud_rate,
            roll_off=si_config.roll_off,
            tx_osnr=si_config.tx_osnr,
            tx_power=request.input_power_dbm
        )

        node_map = {n.uid: n for n in network.nodes()}
        path_elements = []
        for uid in request.path:
            element = node_map.get(uid)
        if element is None:
            raise SimulationError(f"Element with UID '{uid}' from path not found in the network.", status_code=404)
        path_elements.append(element)

    if not path_elements:
        raise SimulationError("Simulation path is empty.", status_code=400)

    path_results = []
    channel_index = 0

    transmitter = path_elements[0]
    if not isinstance(transmitter, Transceiver):
        raise SimulationError(f"Path must start with a Transceiver, but started with {type(transmitter).__name__}.",
                              status_code=400)

    tx_output_power_dbm = request.input_power_dbm
    tx_output_osnr = si_config.tx_osnr

    tx_latency = getattr(transmitter, 'latency', None)
    tx_latency_ms = tx_latency * 1000 if tx_latency is not None else 0

    path_results.append(SimulationStepResult(
        element_id=transmitter.uid,
        element_type=type(transmitter).__name__,
        input_power_dbm=None,
        input_osnr_db=None,
        output_power_dbm=tx_output_power_dbm,
        output_osnr_db=tx_output_osnr,
        added_noise_mw=0,
        details={"latency_ms": tx_latency_ms}
    ))

    for element in path_elements[1:]:
        if isinstance(element, Transceiver):
            break

        input_power_watts = spectral_info.signal[channel_index]
        input_ase_watts = spectral_info.ase[channel_index]
        input_nli_watts = spectral_info.nli[channel_index]
        input_total_noise = input_ase_watts + input_nli_watts
        input_power_dbm = 10 * math.log10(input_power_watts * 1000)
        input_osnr_db = lin2db(input_power_watts / input_total_noise) if input_total_noise > 0 else float('inf')

        element.propagate(spectral_info)

        output_power_watts = spectral_info.signal[channel_index]
        output_ase_watts = spectral_info.ase[channel_index]
        output_nli_watts = spectral_info.nli[channel_index]
        output_total_noise = output_ase_watts + output_nli_watts
        output_power_dbm = 10 * math.log10(output_power_watts * 1000)
        output_osnr_db = lin2db(output_power_watts / output_total_noise) if output_total_noise > 0 else float('inf')

        added_noise_mw = (output_total_noise - input_total_noise) * 1000
        elem_latency = getattr(element, 'latency', None)
        elem_latency_ms = elem_latency * 1000 if elem_latency is not None else 0

        path_results.append(SimulationStepResult(
            element_id=element.uid,
            element_type=type(element).__name__,
            input_power_dbm=round(input_power_dbm, 2),
            input_osnr_db=round(input_osnr_db, 2) if input_osnr_db != float('inf') else None,
            output_power_dbm=round(output_power_dbm, 2),
            output_osnr_db=round(output_osnr_db, 2) if output_osnr_db != float('inf') else None,
            added_noise_mw=added_noise_mw,
            details={"latency_ms": elem_latency_ms}
        ))

    if not path_results:
        raise SimulationError("Simulation failed to produce results.", status_code=500)

    final_osnr = path_results[-1].output_osnr_db if path_results else None
    final_power = path_results[-1].output_power_dbm if path_results else None

    return SingleLinkSimulationResponse(
        path_results=path_results,
        final_osnr_db=final_osnr,
        final_power_dbm=final_power
    )

except Exception as e:
print("--- An exception occurred in GNPy simulation service ---")
traceback.print_exc()
print("---------------------------------------------------------")
raise SimulationError(f"GNPy simulation engine error: {str(e)}", status_code=500)

