import json
from ..models.network import NetworkDetailResponse, NetworkImport, NetworkResponse, SubTopologyImport
from motor.motor_asyncio import AsyncIOMotorDatabase
from ..core.database import get_database
from fastapi import APIRouter, Depends, HTTPException, status
from ..crud import crud_network
from pydantic import ValidationError



async def convert_to_gnpy_json(
        network_id: str,
        db: AsyncIOMotorDatabase = Depends(get_database)
):
    gnpy_elements = []

    db_network = await crud_network.get_network(db, network_id)
    network = NetworkDetailResponse(
        network_id=str(db_network.id),
        **db_network.model_dump(by_alias=True)
    )
    for element in network.elements:
        gnpy_el = {
            "uid": element.element_id,
            "metadata":{
                "location":{
                    "city":"DefaultCity",
                    "region":"DefaultRegion",
                    "latitude":0,
                    "longitude":0
                }
            }
        }

        if element.type == "Transceiver":
            gnpy_el["type"] = "Transceiver"


        elif element.type == "Fiber":
            gnpy_el["type"] = "Fiber"
            gnpy_el["type_variety"] = "SSMF"
            gnpy_el["params"] = {
                "length":element.params.length,
                "att_in":0,
                "con_in":0.5,
                "con_out":0.5,
                "loss_coef":element.params.loss_coef,
                "length_units":"km"
            }

        elif element.type == "Edfa":
            gnpy_el["type"] = "Edfa"
            gnpy_el["type_variety"] = element.type_variety
            gnpy_el["operational"] = {
                "gain_target": element.params.gain_target,
                "att_in": 0,
                "title_target": 0
            }

        gnpy_elements.append(gnpy_el)

    gnpy_connections = []
    for connection in network.connections:
        gnpy_cn = {
            "from_node":connection.from_node,
            "to_node":connection.to_node
        }

        gnpy_connections.append(gnpy_cn)

    print(gnpy_elements)
    print("************************************************************************")
    print(gnpy_connections)

    with open('network.json', 'w', encoding='utf8') as f:
        json.dump(gnpy_elements, f, ensure_ascii=False, indent=4)
        json.dump(gnpy_connections, f, ensure_ascii=False, indent=4)