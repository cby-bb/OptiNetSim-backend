import os
import json
from fastapi import APIRouter, Depends, Body, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from ....core.database import get_database
from ....crud import crud_network
from ....models.network import SingleLinkSimulationRequest, SingleLinkSimulationResponse, NetworkDetailResponse, SimulationResult

router = APIRouter()

class SimulationError(Exception):
    def __init__(self, message, status_code=400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

@router.post(
    "/single-link",
    response_model=SingleLinkSimulationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Single Link Simulation",
)
async def single_link(
        simulation_request: SingleLinkSimulationRequest = Body(...),
        db: AsyncIOMotorDatabase = Depends(get_database)
):
    path_result = []
    db_network = await crud_network.get_network(db, simulation_request.network_id)
    if db_network is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NETWORK_NOT_FOUND", "message": f"Network with id {simulation_request.network_id} not found."}
        )
    source_destination = {
        "source" : simulation_request.source,
        "destination" : simulation_request.destination,
    }

    with open('oopt/gnpy/example-data/node.json', 'w', encoding='utf8') as f:
        json.dump(source_destination, f, ensure_ascii=False, indent=4)

    network = NetworkDetailResponse(
        network_id=str(db_network.id),
        **db_network.model_dump(by_alias=True)
    )
    gnpy_network = {
        "network_name": network.network_name,
        "elements": [],
        "connections": [],
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

    with open('result.json','r',encoding='utf-8') as f:
        result = json.load(f)


    for elt in result['eq_result']:
        if elt['uid'] == element.element_id:
            elt['type'] = element.type
        path_result.append(SimulationResult(
            element_uid = elt["uid"],
            element_type = elt["type"],
            GSNR_01nm = elt["gsnr_0.1nm"],
            GSNR_signal = elt["gsnr_signal"],
            OSNR_ASE_01nm = elt["osnr_ase_0.1nm"],
            OSNR_ASE = elt["osnr_ase_signal"],
        ))

    try:
        return SingleLinkSimulationResponse(
            path_results=path_result,
            GSNR=result["final_GSNR"]
        )
    except SimulationError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)