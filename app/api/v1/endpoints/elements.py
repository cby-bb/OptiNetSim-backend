# app/api/v1/endpoints/elements.py
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from ....core.database import get_database
from ....crud import crud_network
from ....models.network import AnyElementCreate, AnyElementInDB, ElementUpdate

router = APIRouter()


@router.post(
    "",
    response_model=AnyElementInDB,
    status_code=status.HTTP_201_CREATED,
    summary="Add a Topology Element to a Network"
)
async def add_element(
        network_id: str,
        element_in: AnyElementCreate,
        db: AsyncIOMotorDatabase = Depends(get_database)
):
    db_element = await crud_network.add_element_to_network(db, network_id, element_in)
    if db_element is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NETWORK_NOT_FOUND", "message": f"Network with id {network_id} not found."}
        )
    return db_element


@router.get(
    "/{element_id}",
    response_model=AnyElementInDB,
    summary="Get a specific Topology Element by ID"
)
async def get_element(
        network_id: str,
        element_id: str,
        db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Retrieves the detailed information for a specific topology element within a network.
    """
    element = await crud_network.get_element_from_network(db, network_id, element_id)
    if element is None:
        # Differentiate between network not found and element not found in network
        network_exists = await crud_network.get_network(db, network_id)
        if not network_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NETWORK_NOT_FOUND", "message": f"Network with id {network_id} not found."}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "ELEMENT_NOT_FOUND",
                        "message": f"Element with id {element_id} not found in network {network_id}."}
            )
    return element


@router.patch(
    "/{element_id}",
    response_model=AnyElementInDB,
    summary="Update a Topology Element"
)
async def update_element(
        network_id: str,
        element_id: str,
        payload: ElementUpdate,
        db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Updates specific fields of a topology element within a network.
    Only fields provided in the request body will be updated.
    """
    updated_element = await crud_network.update_element_in_network(db, network_id, element_id, payload)
    if updated_element is None:
        network_exists = await crud_network.get_network(db, network_id)
        if not network_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NETWORK_NOT_FOUND", "message": f"Network with id {network_id} not found."}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "ELEMENT_NOT_FOUND",
                        "message": f"Element with id {element_id} not found in network {network_id}."}
            )
    return updated_element


@router.delete(
    "/{element_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a Topology Element"
)
async def delete_element(
        network_id: str,
        element_id: str,
        db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Deletes a specific topology element from a network.
    """
    success = await crud_network.delete_element_from_network(db, network_id, element_id)
    if not success:
        network_exists = await crud_network.get_network(db, network_id)
        if not network_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NETWORK_NOT_FOUND", "message": f"Network with id {network_id} not found."}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "ELEMENT_NOT_FOUND",
                        "message": f"Element with id {element_id} not found in network {network_id}."}
            )
    return None
