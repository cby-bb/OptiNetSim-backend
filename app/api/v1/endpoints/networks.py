from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from ....core.database import get_database
from ....crud import crud_network
from ....models.network import (
    NetworkCreate, NetworkResponse, NetworkListResponse,
    NetworkDetailResponse, NetworkUpdate
)

router = APIRouter()


@router.post(
    "",
    response_model=NetworkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Optical Network"
)
async def create_network(
        network_in: NetworkCreate,
        db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Creates a new, empty optical network with a given name.
    """
    db_network = await crud_network.create_network(db, network=network_in)
    return NetworkResponse(
        network_id=str(db_network.id),
        **db_network.model_dump()
    )


@router.get(
    "",
    response_model=NetworkListResponse,
    summary="Get a list of all Optical Networks"
)
async def get_all_networks(
        page: int = Query(1, ge=1, description="Current page number"),
        limit: int = Query(20, ge=1, le=100, description="Items per page"),
        name_contains: Optional[str] = Query(None, description="Filter by network name (case-insensitive)"),
        sort_by: str = Query("created_at", enum=["created_at", "updated_at", "network_name"]),
        order: str = Query("desc", enum=["asc", "desc"]),
        db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Retrieves a paginated, filterable, and sortable list of all networks.
    """
    networks, total_count = await crud_network.get_all_networks(
        db, page, limit, name_contains, sort_by, order
    )

    response_networks = [
        NetworkResponse(network_id=str(net.id), **net.model_dump())
        for net in networks
    ]

    return NetworkListResponse(
        networks=response_networks,
        total_count=total_count,
        page=page,
        limit=limit
    )


@router.get(
    "/{network_id}",
    response_model=NetworkDetailResponse,
    summary="Get a specific Optical Network by ID"
)
async def get_network(
        network_id: str,
        db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Retrieves the full topology and configuration for a specific network.
    """
    db_network = await crud_network.get_network(db, network_id)
    if db_network is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NETWORK_NOT_FOUND", "message": f"Network with id {network_id} not found"}
        )
    return NetworkDetailResponse(
        network_id=str(db_network.id),
        **db_network.model_dump()
    )


@router.patch(
    "/{network_id}",
    response_model=NetworkResponse,
    summary="Update an Optical Network's name"
)
async def update_network_name(
        network_id: str,
        payload: NetworkUpdate,
        db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Updates the name of a specific network.
    """
    updated_network = await crud_network.update_network(db, network_id, payload)
    if updated_network is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NETWORK_NOT_FOUND", "message": f"Network with id {network_id} not found"}
        )
    return NetworkResponse(
        network_id=str(updated_network.id),
        **updated_network.model_dump()
    )


@router.delete(
    "/{network_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an Optical Network"
)
async def delete_network(
        network_id: str,
        db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Deletes a network and all its associated topology, services, and configurations.
    """
    success = await crud_network.delete_network(db, network_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NETWORK_NOT_FOUND", "message": f"Network with id {network_id} not found"}
        )
    return None
