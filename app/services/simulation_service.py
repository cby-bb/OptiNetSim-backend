import math
import json
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorDatabase
from ..crud import crud_network
from ..models.simulation import SingleLinkSimulationRequest, SingleLinkSimulationResponse, SimulationStepResult
from .gnpy_adapter import convert_to_gnpy_json

# --- GNPy Imports ---
from gnpy.core.equipment import load_equipment
from gnpy.core.network import build_network
from gnpy.core.info import create_input_spectral_information, SpectralInformation
from gnpy.core.utils import db_to_lin
from gnpy.tools.json_io import network_from_json


class SimulationError(Exception):
    def __init__(self, message, status_code=400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


# --- Path to your equipment config ---
# Assumes eqpt_config.json is in the project root
EQPT_CONFIG_PATH = Path(__file__).parent.parent.parent / "eqpt_config.json"


async def simulate_single_link_gnpy(db: AsyncIOMotorDatabase,
                                    request: SingleLinkSimulationRequest) -> SingleLinkSimulationResponse:
    """
    Performs an optical transmission simulation using the GNPy library.
    """
    network_model = await crud_network.get_network(db, request.network_id)
    if not network_model:
        raise SimulationError(f"Network with id {request.network_id} not found.", status_code=404)

    # 1. Convert our API models to a GNPy-compatible JSON structure
    gnpy_network_json = convert_to_gnpy_json(network_model, request.path)

    try:
        # 2. Load GNPy equipment database
        equipment = load_equipment(str(EQPT_CONFIG_PATH))

        # 3. Build the GNPy network graph from our generated JSON
        network = network_from_json(gnpy_network_json, equipment)
        build_network(network, equipment, 0, 0)  # Finalize network build

        # 4. Define the input optical signal (a single 100GHz channel in this case)
        si = create_input_spectral_information(
            f_min=191.35e12, f_max=196.1e12, baud_rate=32e9,
            power=request.input_power_dbm, spacing=50e9, grid_type='flex'
        )
        # Select the first channel for simulation
        power_lin = db_to_lin(request.input_power_dbm) / 1000  # convert dBm to W
        initial_channel = SpectralInformation(
            frequency=si.frequency[0],
            slot_width=si.slot_width[0],
            signal=power_lin,
            nli=0,
            ase=0,
            baud_rate=si.baud_rate[0],
            tx_osnr=None,
            label=None
        )

        # 5. Find the start of the path and propagate the signal
        start_node_uid = request.path[0]
        start_node = next(n for n in network.nodes() if n.uid == start_node_uid)

        path_results = []

        # The propagate function is a generator, yielding results at each element
        for element, si_out in network.propagate(start_node, initial_channel):
            si_in = si_out.tx_in_path[-1]  # Spectral info at element input

            # Convert GNPy's linear results back to dB/dBm
            input_power_dbm = 10 * math.log10(si_in.signal * 1000)
            output_power_dbm = 10 * math.log10(si_out.signal * 1000)

            # GNPy OSNR is calculated over a 0.1nm reference bandwidth
            input_osnr_db = 10 * math.log10(si_in.signal / si_in.ase) if si_in.ase > 0 else None
            output_osnr_db = 10 * math.log10(si_out.signal / si_out.ase) if si_out.ase > 0 else None

            path_results.append(SimulationStepResult(
                element_id=element.uid,
                element_type=element.type.capitalize(),
                input_power_dbm=input_power_dbm,
                input_osnr_db=input_osnr_db,
                output_power_dbm=output_power_dbm,
                output_osnr_db=output_osnr_db,
                added_noise_mw=(si_out.ase - si_in.ase) * 1000,
                details={"latency_ms": element.latency * 1000}  # Example of extra detail from GNPy
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
        # Catch potential errors from GNPy and return a user-friendly message
        raise SimulationError(f"GNPy simulation engine error: {e}", status_code=500)

