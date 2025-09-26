# app/api/v1/endpoints/import_export.py
import json
import os
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import ValidationError  # 导入 ValidationError

from ....core.database import get_database
from ....crud import crud_network
from ....models.network import NetworkDetailResponse, NetworkImport, NetworkResponse, SubTopologyImport
from oopt.gnpy.tools.cli_examples import transmission_main_example


router = APIRouter()


@router.get(
    "/{network_id}/export",
    response_model=NetworkDetailResponse,
    summary="Export a Network"
)
async def export_network(
        network_id: str,
        db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Exports a specified optical network, including its structure, global settings, and services.
    """
    db_network = await crud_network.get_network(db, network_id)
    if db_network is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NETWORK_NOT_FOUND", "message": f"Network with id {network_id} not found."}
        )
    # NetworkDetailResponse automatically handles the alias mapping for SI/Span
    network = NetworkDetailResponse(
        network_id=str(db_network.id),
        **db_network.model_dump(by_alias=True)
    )
    gnpy_network = {
        "network_name": network.network_name,
        "elements":[],
        "connections":[],
    }
    for element in network.elements:
        gnpy_el = {
            "uid": element.element_id,
            "metadata": {
                "location": {
                    "city": "DefaultCity",
                    "region": "DefaultRegion",
                    "latitude": 0,
                    "longitude": 0
                }
            }
        }

        if element.type == "Transceiver":
            gnpy_el["type"] = "Transceiver"


        elif element.type == "Fiber":
            gnpy_el["type"] = "Fiber"
            gnpy_el["type_variety"] = "SSMF"
            gnpy_el["params"] = {
                "length": element.params.length,
                "att_in": 0,
                "con_in": 0.5,
                "con_out": 0.5,
                "loss_coef": element.params.loss_coef,
                "length_units": "km"
            }

        elif element.type == "Edfa":
            gnpy_el["type"] = "Edfa"
            gnpy_el["type_variety"] = element.type_variety
            gnpy_el["operational"] = {
                "gain_target": element.params.gain_target,
                "att_in": 0,
                "title_target": 0
            }

        gnpy_network["elements"].append(gnpy_el)

    gnpy_connections = []
    for connection in network.connections:
        gnpy_cn = {
            "from_node": connection.from_node,
            "to_node": connection.to_node
        }

        gnpy_network["connections"].append(gnpy_cn)
    with open('oopt/gnpy/example-data/network.json', 'w', encoding='utf8') as f:
        json.dump(gnpy_network, f, ensure_ascii=False, indent=4)
    command_str = "python oopt/gnpy/tools/cli_examples.py"
    os.system(command_str)
    return NetworkDetailResponse(
        network_id=str(db_network.id),
        **db_network.model_dump(by_alias=True)  # Ensure aliases are used for export
    )


@router.post(
    "/import",
    response_model=NetworkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Import a new Network"
)
async def import_network(
        network_in: NetworkImport,
        db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Imports a complete network structure, creating a new network in the system.
    Server will generate new IDs for all elements, connections, and services.
    """
    try:
        db_network = await crud_network.create_network_from_import(db, network_in)
        return NetworkResponse(
            network_id=str(db_network.id),
            **db_network.model_dump()
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_IMPORT_DATA", "message": "Invalid data provided for network import.",
                    "details": e.errors()}
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "IMPORT_PROCESSING_ERROR", "message": str(e)}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_SERVER_ERROR",
                "message": f"An unexpected error occurred during network import. {str(e)}"
            }
        )


@router.post(
    "/{network_id}/import",
    response_model=NetworkResponse,
    summary="Insert Topology into an Existing Network"
)
async def insert_topology(
        network_id: str,
        sub_topology_in: SubTopologyImport,
        db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Inserts a sub-topology (elements and connections) into an existing network.
    Existing network's global settings (SI, Span, SimulationConfig) are not affected.
    """
    try:
        updated_network = await crud_network.insert_sub_topology(db, network_id, sub_topology_in)
        if updated_network is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NETWORK_NOT_FOUND", "message": f"Network with id {network_id} not found."}
            )
        return NetworkResponse(
            network_id=str(updated_network.id),
            **updated_network.model_dump()
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_INSERT_DATA", "message": "Invalid data provided for topology insertion.",
                    "details": e.errors()}
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,  # Use 409 for conflicts, as per docs
            detail={"code": "RESOURCE_CONFLICT", "message": str(e)}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_SERVER_ERROR",
                    "message": f"An unexpected error occurred during topology insertion. {str(e)}"}
        )
