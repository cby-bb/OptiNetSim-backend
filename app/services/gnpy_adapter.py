from typing import List, Dict, Any
from ..models.network import NetworkInDB, DiscriminatedElementInDB
from fastapi import HTTPException  # <--- 导入 HTTPException
from starlette import status       # <--- 导入 status


def convert_to_gnpy_json(network: NetworkInDB, path: List[str]) -> Dict[str, Any]:
    """
    Converts a network and a specific path into a GNPy-compatible JSON structure in memory.
    """
    gnpy_elements = []

    # Filter only the elements in the specified path
    path_elements = [el for el in network.elements if el.element_id in path]
    # Maintain the order specified in the path
    if len(path_elements) != len(path):
        found_ids = {el.element_id for el in path_elements}
        missing_ids = [pid for pid in path if pid not in found_ids]
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"The following element_ids from the path were not found in the network: {missing_ids}"
        )
    ordered_path_elements = sorted(path_elements, key=lambda el: path.index(el.element_id))

    for element in ordered_path_elements:
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

        # --- Parameter Mapping ---
        if element.type == "Transceiver":
            gnpy_el["type"] = "Transceiver"
            # In GNPy, Transceiver is mainly a placeholder for the start/end of the simulation
            # We will define the signal properties separately.

        elif element.type == "Fiber":
            gnpy_el["type"] = "Fiber"
            gnpy_el["params"] = {
                "length": element.params.length,
                "length_units": 'km',
                "att_in": 0,
                "con_in": 0.5,  # Default connector loss
                "con_out": 0.5,
                "type_variety": "SSMF",  # Assume Standard Single-Mode Fiber
                "loss_coef": "element.params.loss_coef",
                "dispersion":"element.params.dispersion",
                "gamma":"element.params.gamma"
            }

        elif element.type == "Edfa":
            gnpy_el["type"] = "Edfa"
            # Use the 'default' EDFA type we defined in eqpt_config.json
            gnpy_el["type_variety"] = "default"
            gnpy_el["params"] = {
                # Override default operational parameters with our model's data
                "operational": {
                    "gain_target": element.params.gain_target,
                    "att_in": 0,
                    "tilt_target": 0
                }
            }
            # Note: We let GNPy calculate noise figure based on its internal model
            # specified in eqpt_config.json for higher accuracy.

        elif element.type == "Roadm":
            gnpy_el["type"] = "Roadm"
            gnpy_el["params"] = {
                # ROADMs have complex models in GNPy, here is a simplified version
                "att_in": 0,
                "per_degree_impairments": {
                    "default": {
                        "add_drop_osnr": 48,
                        "pmd": 0.05,
                        "cd": 2
                    }
                }
            }

        gnpy_elements.append(gnpy_el)

    # --- Generate Connections ---
    gnpy_connections = []
    for i in range(len(path) - 1):
        gnpy_connections.append({
            "from_node": path[i],
            "to_node": path[i + 1],
            "from_node_port": 1,  # Using simple port numbers
            "to_node_port": 1
        })

    return {
        "elements": gnpy_elements,
        "connections": gnpy_connections
    }
