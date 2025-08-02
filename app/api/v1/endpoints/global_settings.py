# app/api/v1/endpoints/global_settings.py
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from ....core.database import get_database
from ....crud import crud_network
from ....models.network import SI, Span, SimulationConfig

router = APIRouter()


@router.patch(
    "/simulation-config",
    response_model=SimulationConfig,
    summary="Update Network Simulation Configuration"
)
async def update_network_simulation_config(
        network_id: str,
        payload: SimulationConfig,
        db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Updates the simulation global settings for a specific optical network.
    Only fields provided in the request body will be updated.
    """
    updated_config = await crud_network.update_simulation_config(db, network_id, payload)
    if updated_config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NETWORK_NOT_FOUND", "message": f"Network with id {network_id} not found."}
        )
    return updated_config


@router.patch(
    "/spectrum-information",
    response_model=SI,
    summary="Update Network Spectrum Information (SI)"
)
async def update_network_si(
        network_id: str,
        payload: SI,
        db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Updates the Spectrum Information (SI) global settings for a specific optical network.
    Only fields provided in the request body will be updated.
    """
    updated_si = await crud_network.update_si_config(db, network_id, payload)
    if updated_si is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NETWORK_NOT_FOUND", "message": f"Network with id {network_id} not found."}
        )
    return updated_si


@router.patch(
    "/span-parameters",
    response_model=Span,
    summary="Update Network Span Parameters"
)
async def update_network_span(
        network_id: str,
        payload: Span,
        db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Updates the Span parameters global settings for a specific optical network.
    Only fields provided in the request body will be updated.
    """
    updated_span = await crud_network.update_span_config(db, network_id, payload)
    if updated_span is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NETWORK_NOT_FOUND", "message": f"Network with id {network_id} not found."}
        )
    return updated_span
