from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class SingleLinkSimulationRequest(BaseModel):
    """
    Request model for a single link transmission simulation.
    """
    network_id: str = Field(..., description="The ID of the network to simulate within.")
    path: List[str] = Field(..., description="An ordered list of element_ids representing the transmission path.")
    input_power_dbm: float = Field(0.0, description="Initial input power of the optical signal in dBm.")

class SimulationStepResult(BaseModel):
    """
    Results of the simulation at each step (after each element).
    """
    element_id: str
    element_type: str
    input_power_dbm: float
    input_osnr_db: Optional[float]
    output_power_dbm: float
    output_osnr_db: Optional[float]
    added_noise_mw: float = Field(..., description="Noise power added by this element in mW.")
    details: Dict[str, Any] = Field({}, description="Additional element-specific simulation details (e.g., gain, loss).")

class SingleLinkSimulationResponse(BaseModel):
    """
    Response model containing the step-by-step results of the simulation.
    """
    path_results: List[SimulationStepResult]
    final_osnr_db: Optional[float] = Field(..., description="The final OSNR at the end of the link.")
    final_power_dbm: float = Field(..., description="The final signal power at the end of the link.")

