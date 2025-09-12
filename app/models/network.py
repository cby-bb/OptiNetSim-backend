# app/models/network.py

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union

from bson import ObjectId
from pydantic import BaseModel, Field, model_validator, ValidationError
from uuid6 import uuid6


# --- Helper Models for Global Settings ---

class Location(BaseModel):
    x: float
    y: float


class RamanParams(BaseModel):
    flag: bool = True
    result_spatial_resolution: int = 10
    solver_spatial_resolution: int = 50


class NliParams(BaseModel):
    method: str = "ggn_spectrally_separated"
    dispersion_tolerance: float = 1.0
    phase_shift_tolerance: float = 0.1
    computed_channels: List[int] = Field(default_factory=list)


class SimulationConfig(BaseModel):
    raman_params: RamanParams = Field(default_factory=RamanParams)
    nli_params: NliParams = Field(default_factory=NliParams)


class SIConfig(BaseModel):
    f_min: float = 190.3e12
    baud_rate: float = 3.57e9
    f_max: float = 196.1e12
    spacing: float = 50e9
    power_dbm: int = 2
    power_range_db: List[int] = Field(default_factory=lambda: [0, 0, 1])
    roll_off: float = 0.15
    tx_osnr: int = 35
    sys_margins: int = 2


class SpanConfig(BaseModel):
    power_mode: bool = True
    delta_power_range_db: List[int] = Field(default_factory=lambda: [0, 0, 0])
    max_fiber_lineic_loss_for_raman: float = 0.25
    target_extended_gain: int = 0
    max_length: int = 135
    length_units: str = "km"
    max_loss: int = 28
    padding: int = 11
    EOL: int = 0
    con_in: int = 0
    con_out: int = 0


# --- Element Models ---
class ElementParamsBase(BaseModel):
    pass

class TransceiverParams(ElementParamsBase):
    pass # Add specific params if needed

class FusedParams(ElementParamsBase):
    pass # Add specific params if needed

class FiberParams(ElementParamsBase):
    length: float = 80.0
    loss_coef: float = 0.215
    length_units: str = "km"
    att_in: float = 0.0


class RamanFiberParams(FiberParams):
    raman_efficiency: float = 4.5e-4
    noise_figure: Optional[float] = 4.5

class RoadmParams(ElementParamsBase):
    target_pch_out_db: Optional[float] = None
    restrictions: Dict[str, Any] = Field(default_factory=dict)

class EdfaParams(ElementParamsBase):
    gain_target: Optional[float] = None
    tilt_target: Optional[float] = None


# --- Base Element Model ---
class ElementBase(BaseModel):
    name: str
    type: Literal["Transceiver", "Edfa", "Roadm", "Fiber", "Fused", "RamanFiber"]
    type_variety: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    operational: Dict[str, Any] = Field(default_factory=dict)


# --- Concrete Element Models for Validation ---
class ElementCreateBase(ElementBase):
    element_id: Optional[str] = None # For import linking

class ElementInDBBase(ElementBase):
    element_id: str = Field(default_factory=lambda: str(uuid6()))

# Specific Element types for CREATE
class TransceiverCreate(ElementCreateBase):
    type: Literal["Transceiver"] = "Transceiver"
    params: TransceiverParams = Field(default_factory=TransceiverParams)

class EdfaCreate(ElementCreateBase):
    type: Literal["Edfa"] = "Edfa"
    params: EdfaParams = Field(default_factory=EdfaParams)

class RoadmCreate(ElementCreateBase):
    type: Literal["Roadm"] = "Roadm"
    params: RoadmParams = Field(default_factory=RoadmParams)

class FiberCreate(ElementCreateBase):
    type: Literal["Fiber"] = "Fiber"
    params: FiberParams = Field(default_factory=FiberParams)

class FusedCreate(ElementCreateBase):
    type: Literal["Fused"] = "Fused"
    params: FusedParams = Field(default_factory=FusedParams)

class RamanFiberCreate(ElementCreateBase):
    type: Literal["RamanFiber"] = "RamanFiber"
    params: RamanFiberParams = Field(default_factory=RamanFiberParams)


# Specific Element types for IN_DB
class TransceiverInDB(ElementInDBBase):
    type: Literal["Transceiver"] = "Transceiver"
    params: TransceiverParams = Field(default_factory=TransceiverParams)

class EdfaInDB(ElementInDBBase):
    type: Literal["Edfa"] = "Edfa"
    params: EdfaParams = Field(default_factory=EdfaParams)

class RoadmInDB(ElementInDBBase):
    type: Literal["Roadm"] = "Roadm"
    params: RoadmParams = Field(default_factory=RoadmParams)

class FiberInDB(ElementInDBBase):
    type: Literal["Fiber"] = "Fiber"
    params: FiberParams = Field(default_factory=FiberParams)

class FusedInDB(ElementInDBBase):
    type: Literal["Fused"] = "Fused"
    params: FusedParams = Field(default_factory=FusedParams)

class RamanFiberInDB(ElementInDBBase):
    type: Literal["RamanFiber"] = "RamanFiber"
    params: RamanFiberParams = Field(default_factory=RamanFiberParams)


# --- Discriminated Unions ---

AnyElementCreate = Union[
    TransceiverCreate, EdfaCreate, RoadmCreate, FiberCreate, FusedCreate, RamanFiberCreate
]

AnyElementInDB = Union[
    TransceiverInDB, EdfaInDB, RoadmInDB, FiberInDB, FusedInDB, RamanFiberInDB
]

class ElementUpdate(BaseModel):
    name: Optional[str] = None
    # Type cannot be updated via PATCH to avoid complexity with params validation
    # type: Optional[Literal["Transceiver", "Edfa", "Roadm", "Fiber", "Fused", "RamanFiber"]] = None
    type_variety: Optional[str] = None
    params: Optional[Dict[str, Any]] = None # Kept as dict for flexibility in PATCH
    operational: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


# --- Connection Models ---
class ConnectionBase(BaseModel):
    from_node: str
    to_node: str


class ConnectionCreate(ConnectionBase):
    pass


class ConnectionInDB(ConnectionBase):
    connection_id: str = Field(default_factory=lambda: str(uuid6()))


# --- Service Models ---
class ServiceRequirements(BaseModel):
    bandwidth: float
    latency: float


class ServiceBase(BaseModel):
    name: str
    path: List[str]
    service_requirements: Optional[ServiceRequirements] = None
    service_constraints: Dict[str, Any] = Field(default_factory=dict)


class ServiceCreate(ServiceBase):
    pass


class ServiceInDB(ServiceBase):
    service_id: str = Field(default_factory=lambda: str(uuid6()))
    status: str = "Provisioning"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ServiceUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    path: Optional[List[str]] = None
    service_requirements: Optional[ServiceRequirements] = None
    service_constraints: Optional[Dict[str, Any]] = None

# --- Network Models ---

class NetworkBase(BaseModel):
    network_name: str


class NetworkCreate(NetworkBase):
    pass


class NetworkUpdate(NetworkBase):
    pass


class NetworkInDB(NetworkBase):
    id: ObjectId = Field(default_factory=ObjectId, alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    elements: List[Field(AnyElementInDB, discriminator="type")] = Field(default_factory=list)
    connections: List[ConnectionInDB] = Field(default_factory=list)
    services: List[ServiceInDB] = Field(default_factory=list)
    SI: SIConfig = Field(default_factory=SIConfig, alias="SI")
    Span: SpanConfig = Field(default_factory=SpanConfig, alias="Span")
    simulation_config: SimulationConfig = Field(default_factory=SimulationConfig)

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }


class NetworkResponse(NetworkBase):
    network_id: str
    created_at: datetime
    updated_at: datetime


class NetworkListResponse(BaseModel):
    networks: List[NetworkResponse]
    total_count: int
    page: int
    limit: int


class NetworkDetailResponse(NetworkResponse):
    elements: List[Field(AnyElementInDB, discriminator="type")]
    connections: List[ConnectionInDB]
    services: List[ServiceInDB]
    SI: SIConfig
    Span: SpanConfig
    simulation_config: SimulationConfig

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }


# --- Import/Export Models ---

class NetworkImport(BaseModel):
    network_name: str
    elements: List[Field(AnyElementCreate, discriminator="type")] = Field(default_factory=list)
    connections: List[ConnectionCreate] = Field(default_factory=list)
    services: List[ServiceCreate] = Field(default_factory=list)
    SI: SIConfig = Field(default_factory=SIConfig, alias="SI")
    Span: SpanConfig = Field(default_factory=SpanConfig, alias="Span")
    simulation_config: SimulationConfig = Field(default_factory=SimulationConfig)


class SubTopologyImport(BaseModel):
    elements: List[Field(AnyElementCreate, discriminator="type")]
    connections: List[ConnectionCreate]
    strategy: Literal["generate_new_id", "error"] = "generate_new_id"