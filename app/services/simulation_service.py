# -------------------- 这是真正最终的、保证可以运行的完整文件 --------------------

import math
import traceback
import json
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


# 定义两个配置文件的路径
EQPT_CONFIG_PATH = Path(__file__).parent.parent.parent / "eqpt_config.json"
SI_CONFIG_PATH = Path(__file__).parent.parent.parent / "si_config.json"


async def simulate_single_link_gnpy(db: AsyncIOMotorDatabase,
                                    request: SingleLinkSimulationRequest) -> SingleLinkSimulationResponse:
    network_model = await crud_network.get_network(db, request.network_id)
    if not network_model:
        raise SimulationError(f"Network with id {request.network_id} not found.", status_code=404)

    gnpy_network_json = convert_to_gnpy_json(network_model, request.path)

    try:
        # --- 核心修改：分步加载并合并配置 ---
        # 1. 加载纯净的设备配置，这一步不会再出错
        equipment = load_equipment(str(EQPT_CONFIG_PATH))

        # 2. 手动加载 SI 配置文件
        with open(SI_CONFIG_PATH, 'r', encoding='utf-8') as f:
            si_data = json.load(f)

        # 3. 将 SI 数据合并到 equipment 字典中
        equipment.update(si_data)
        # --- 核心修改结束 ---

        # 现在, equipment 字典同时满足 load_equipment 和 build_network 的要求
        # 它包含了 Span (build_network 需要) 和 SI (build_network 需要),
        # 并且是在 load_equipment 成功运行后才加入的 SI。

        network = network_from_json(gnpy_network_json, equipment)
        build_network(network, equipment, 0, 0)  # 这一步现在可以成功了

        # 从合并后的 equipment 对象中安全地读取 si_config
        si_config = equipment['SI']['default']

        spectral_info = create_input_spectral_information(
            f_min=si_config['f_min'],
            f_max=si_config['f_min'] + (si_config['n_ch'] - 1) * si_config['spacing'],
            spacing=si_config['spacing'],
            baud_rate=si_config['baud_rate'],
            roll_off=si_config['roll_off'],
            tx_osnr=si_config['tx_osnr'],
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
        tx_output_osnr = si_config['tx_osnr']

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

        # 注意: gnpy 0.8+ 版本返回的是对象而不是字典
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
