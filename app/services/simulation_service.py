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


EQPT_CONFIG_PATH = Path(__file__).parent.parent.parent / "eqpt_config.json"


async def simulate_single_link_gnpy(db: AsyncIOMotorDatabase,
                                    request: SingleLinkSimulationRequest) -> SingleLinkSimulationResponse:
    network_model = await crud_network.get_network(db, request.network_id)
    if not network_model:
        raise SimulationError(f"Network with id {request.network_id} not found.", status_code=404)

    gnpy_network_json = convert_to_gnpy_json(network_model, request.path)

    try:
        # 加载纯净的设备配置，这个调用现在不会再出错了
        equipment = load_equipment(str(EQPT_CONFIG_PATH))

        network = network_from_json(gnpy_network_json, equipment)
        build_network(network, equipment, 0, 0)

        # --- 核心修改：不再从配置文件读取SI，而是在代码中直接定义 ---
        # 我们将之前在 JSON 中的 SI 参数直接写在这里
        # 注意：baud_rate, roll_off, tx_osnr 等参数可能需要根据你的 Transceiver 定义来调整
        # 这里使用了 gnpy 中常见的默认值
        default_baud_rate = 32e9  # 对应 QPSK 模式
        default_roll_off = 0.15
        default_tx_osnr = 45  # 设定一个合理的发射 OSNR

        spectral_info = create_input_spectral_information(
            f_min=191.35e12,
            f_max=191.35e12 + (96 - 1) * 50e9,  # f_min + (N-1)*spacing
            spacing=50e9,
            baud_rate=default_baud_rate,
            roll_off=default_roll_off,
            tx_osnr=default_tx_osnr,
            tx_power=request.input_power_dbm  # 使用请求中的输入功率
        )
        # --- 核心修改结束 ---

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
        # 我们只关心第一个信道的结果作为示例
        channel_index = 0

        transmitter = path_elements[0]
        if not isinstance(transmitter, Transceiver):
            raise SimulationError(f"Path must start with a Transceiver, but started with {type(transmitter).__name__}.",
                                  status_code=400)

        tx_output_power_dbm = request.input_power_dbm
        tx_output_osnr = default_tx_osnr

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

        # 从第二个设备开始传播
        for element in path_elements[1:]:
            # 如果路径中遇到另一个收发器，则停止
            if isinstance(element, Transceiver):
                break

            # 记录传播前的状态
            input_power_watts = spectral_info.signal[channel_index]
            input_ase_watts = spectral_info.ase[channel_index]
            input_nli_watts = spectral_info.nli[channel_index]
            input_total_noise = input_ase_watts + input_nli_watts
            input_power_dbm = 10 * math.log10(input_power_watts * 1000)
            input_osnr_db = lin2db(input_power_watts / input_total_noise) if input_total_noise > 0 else float('inf')

            # 核心传播步骤
            element.propagate(spectral_info)

            # 记录传播后的状态
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

