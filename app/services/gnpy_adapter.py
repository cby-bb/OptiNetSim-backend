# -------------------- 这是全新的、完整的、健壮的适配器文件 --------------------

from typing import List, Dict, Any
from ..models.network import Network

# 一个从我们的前端节点类型到 GNPy 期望的类型/参数的映射。
# 这使得适配器更易于维护。
GNPY_TYPE_MAPPING = {
    "Transceiver": "Transceiver",
    "Roadm": "Roadm",
    "Edfa": "Edfa",
    "Fiber": "Fiber",
}


def convert_to_gnpy_json(network_model: Network, path: List[str]) -> Dict[str, Any]:
    """
    将网络模型和指定路径转换为 GNPy 兼容的 JSON 结构。
    """
    gnpy_elements = []

    # 1. 为 GNPy 创建元素定义
    for node in network_model.nodes:
        # 我们只需要包含实际在请求路径中的元素
        if node.id not in path:
            continue

        gnpy_type = GNPY_TYPE_MAPPING.get(node.type)
        if not gnpy_type:
            # 对于未知的节点类型，跳过或引发错误
            continue

        element_def = {
            "uid": node.id,
            "type": gnpy_type,
            "metadata": {
                "location": {
                    "city": node.label,
                    "latitude": node.y,
                    "longitude": node.x
                }
            }
        }

        # 在 GNPy 中，光纤不是节点，而是由其参数定义。
        # 我们在创建连接时处理它们。在这里，如果需要特定的覆盖，
        # 我们可以添加一个 'params' 键，但目前我们依赖于 equipment.json 中的 'default' 类型。
        # 对于放大器 (Edfa)，如果不是默认类型，我们可以指定 'type_variety'。
        if gnpy_type in ["Edfa", "Roadm", "Transceiver"]:
            element_def["params"] = {
                "type_variety": "default"
            }

        gnpy_elements.append(element_def)

    # 2. 为 GNPy 创建连接定义
    gnpy_connections = []

    # 遍历路径以创建有向连接
    for i in range(len(path) - 1):
        from_node_id = path[i]
        to_node_id = path[i + 1]

        # 在网络模型中找到与此路径段对应的链路
        # 这里假设是一个双向链路模型，我们不关心 source/target 的方向来查找链路。
        link_data = None
        for link in network_model.links:
            if (link.source == from_node_id and link.target == to_node_id) or \
                    (link.source == to_node_id and link.target == from_node_id):
                link_data = link
                break

        if not link_data:
            # 如果路径有效，这理想情况下不应该发生
            raise ValueError(f"无法找到 {from_node_id} 和 {to_node_id} 之间的链路")

        # 在 GNPy 中，一个光纤跨段是具有特定参数的连接
        connection_def = {
            "from_node": from_node_id,
            "to_node": to_node_id,
            "params": {
                # 我们假设链路代表一个默认的光纤跨段
                "type": "Span",
                "type_variety": "default"
            }
        }
        gnpy_connections.append(connection_def)

    # 3. 组装最终的 GNPy JSON 对象
    gnpy_network_json = {
        "elements": gnpy_elements,
        "connections": gnpy_connections
    }

    return gnpy_network_json

