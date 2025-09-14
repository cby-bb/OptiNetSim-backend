from fastapi import APIRouter, Depends, Body, HTTPException

from ....core.database import get_database
from ....services import simulation_service
from ....services.simulation_service import SimulationError
from ....models.simulation import SingleLinkSimulationRequest, SingleLinkSimulationResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

router = APIRouter()


@router.post(
    "/single-link",
    response_model=SingleLinkSimulationResponse,
    summary="Simulate a Single Link Transmission (using GNPy Engine)"
)
async def run_single_link_simulation(
        simulation_request: SingleLinkSimulationRequest = Body(...),
        db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Runs a physical layer simulation using the GNPy engine.

    The simulation calculates power levels and OSNR degradation across a specified
    path of network elements.

    - **network_id**: The network containing the elements.
    - **path**: An ordered list of `element_id`s defining the light path.
    - **input_power_dbm**: The initial power launched into the first element.
    """
    try:
        # MODIFIED: Call the new GNPy-based simulation function
        results = await simulation_service.simulate_single_link_gnpy(db, simulation_request)
        return results
    except SimulationError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
