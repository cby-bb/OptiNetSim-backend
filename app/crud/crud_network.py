from datetime import datetime
from typing import List, Optional, Dict, Any
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from ..models.network import (
    NetworkCreate, NetworkInDB, NetworkUpdate, ElementCreate, ElementInDB,
    ElementUpdate, ConnectionCreate, ConnectionInDB, ServiceCreate, ServiceInDB, ServiceUpdate,
    NetworkImport, SubTopologyImport
)

COLLECTION = "networks"


# --- Network CRUD ---

async def create_network(db: AsyncIOMotorDatabase, network: NetworkCreate) -> NetworkInDB:
    network_data = network.model_dump()
    now = datetime.utcnow()
    db_network = NetworkInDB(**network_data, created_at=now, updated_at=now)

    # Using model_dump(by_alias=True) to respect the '_id' alias
    await db[COLLECTION].insert_one(db_network.model_dump(by_alias=True))
    return db_network


async def get_network(db: AsyncIOMotorDatabase, network_id: str) -> Optional[NetworkInDB]:
    if not ObjectId.is_valid(network_id):
        return None
    doc = await db[COLLECTION].find_one({"_id": ObjectId(network_id)})
    return NetworkInDB(**doc) if doc else None


async def get_all_networks(
        db: AsyncIOMotorDatabase,
        page: int,
        limit: int,
        name_contains: Optional[str],
        sort_by: str,
        order: str
) -> (List[NetworkInDB], int):
    query = {}
    if name_contains:
        query["network_name"] = {"$regex": name_contains, "$options": "i"}

    total_count = await db[COLLECTION].count_documents(query)

    sort_order = 1 if order == "asc" else -1
    cursor = db[COLLECTION].find(query).sort(sort_by, sort_order).skip((page - 1) * limit).limit(limit)

    networks = [NetworkInDB(**doc) async for doc in cursor]
    return networks, total_count


async def update_network(db: AsyncIOMotorDatabase, network_id: str, payload: NetworkUpdate) -> Optional[NetworkInDB]:
    if not ObjectId.is_valid(network_id):
        return None

    update_data = payload.model_dump(exclude_unset=True)
    update_data["updated_at"] = datetime.utcnow()

    result = await db[COLLECTION].find_one_and_update(
        {"_id": ObjectId(network_id)},
        {"$set": update_data},
        return_document=True
    )
    return NetworkInDB(**result) if result else None


async def delete_network(db: AsyncIOMotorDatabase, network_id: str) -> bool:
    if not ObjectId.is_valid(network_id):
        return False
    result = await db[COLLECTION].delete_one({"_id": ObjectId(network_id)})
    return result.deleted_count > 0


# --- Sub-document (Element, Connection, Service) CRUD ---

async def add_element_to_network(db: AsyncIOMotorDatabase, network_id: str, element: ElementCreate) \
        -> Optional[ElementInDB]:
    new_element = ElementInDB(**element.model_dump())
    result = await db[COLLECTION].update_one(
        {"_id": ObjectId(network_id)},
        {
            "$push": {"elements": new_element.model_dump()},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    return new_element if result.modified_count > 0 else None


async def update_element_in_network(db: AsyncIOMotorDatabase, network_id: str, element_id: str,
                                    payload: ElementUpdate) -> Optional[ElementInDB]:
    update_data = {f"elements.$.{key}": val for key, val in payload.model_dump(exclude_unset=True).items()}
    if not update_data:
        # If payload is empty, just fetch the element
        network = await get_network(db, network_id)
        if network:
            return next((el for el in network.elements if el.element_id == element_id), None)
        return None

    update_data["updated_at"] = datetime.utcnow()

    result = await db[COLLECTION].update_one(
        {"_id": ObjectId(network_id), "elements.element_id": element_id},
        {"$set": update_data}
    )
    if result.modified_count > 0:
        updated_network = await get_network(db, network_id)
        return next((el for el in updated_network.elements if el.element_id == element_id), None)
    return None


async def delete_element_from_network(db: AsyncIOMotorDatabase, network_id: str, element_id: str) -> bool:
    result = await db[COLLECTION].update_one(
        {"_id": ObjectId(network_id)},
        {
            "$pull": {"elements": {"element_id": element_id}},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    return result.modified_count > 0


async def add_connection_to_network(db: AsyncIOMotorDatabase, network_id: str, connection: ConnectionCreate) -> \
        Optional[ConnectionInDB]:
    new_connection = ConnectionInDB(**connection.model_dump())
    result = await db[COLLECTION].update_one(
        {"_id": ObjectId(network_id)},
        {
            "$push": {"connections": new_connection.model_dump()},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    return new_connection if result.modified_count > 0 else None


async def delete_connection_from_network(db: AsyncIOMotorDatabase, network_id: str, connection_id: str) -> bool:
    result = await db[COLLECTION].update_one(
        {"_id": ObjectId(network_id)},
        {
            "$pull": {"connections": {"connection_id": connection_id}},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    return result.modified_count > 0


# ... (Implement similar CRUD for Services)

# --- Global Settings Update ---

async def update_global_setting(db: AsyncIOMotorDatabase, network_id: str, setting_name: str,
                                payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    update_data = {f"{setting_name}.{k}": v for k, v in payload.items()}
    update_data["updated_at"] = datetime.utcnow()

    result = await db[COLLECTION].find_one_and_update(
        {"_id": ObjectId(network_id)},
        {"$set": update_data},
        return_document=True
    )
    return result.get(setting_name) if result else None


# --- Import/Export ---

async def create_network_from_import(db: AsyncIOMotorDatabase, import_data: NetworkImport) -> NetworkInDB:
    # Create new elements with new IDs, keeping a map from old to new
    element_id_map = {}
    elements_in_db = []
    for el_create in import_data.elements:
        old_id = el_create.name  # Assuming name is a temporary unique ID, or you can add a temp_id field
        new_element = ElementInDB(**el_create.model_dump(exclude={"element_id"}))
        elements_in_db.append(new_element)
        element_id_map[old_id] = new_element.element_id

    # Create new connections using the new element IDs
    connections_in_db = []
    for conn_create in import_data.connections:
        new_from = element_id_map.get(conn_create.from_node)
        new_to = element_id_map.get(conn_create.to_node)
        if new_from and new_to:
            new_conn = ConnectionInDB(from_node=new_from, to_node=new_to)
            connections_in_db.append(new_conn)

    # Create the network document
    now = datetime.utcnow()
    network_doc = {
        "network_name": import_data.network_name,
        "created_at": now,
        "updated_at": now,
        "elements": [el.model_dump() for el in elements_in_db],
        "connections": [conn.model_dump() for conn in connections_in_db],
        "services": [ServiceInDB(**s.model_dump()).model_dump() for s in import_data.services],
        "SI": import_data.SI.model_dump(),
        "Span": import_data.Span.model_dump(),
        "simulation_config": import_data.simulation_config.model_dump(),
    }

    result = await db[COLLECTION].insert_one(network_doc)
    created_doc = await db[COLLECTION].find_one({"_id": result.inserted_id})
    return NetworkInDB(**created_doc)


async def insert_sub_topology(db: AsyncIOMotorDatabase, network_id: str, sub_topo: SubTopologyImport) -> bool:
    # This is a complex operation. For simplicity, we'll just add new elements and connections.
    # A real implementation would need to handle ID conflicts based on the 'strategy'.
    elements_to_add = [ElementInDB(**el.model_dump()).model_dump() for el in sub_topo.elements]
    connections_to_add = [ConnectionInDB(**c.model_dump()).model_dump() for c in sub_topo.connections]

    result = await db[COLLECTION].update_one(
        {"_id": ObjectId(network_id)},
        {
            "$push": {
                "elements": {"$each": elements_to_add},
                "connections": {"$each": connections_to_add}
            },
            "$set": {"updated_at": datetime.utcnow()}
        }
    )
    return result.modified_count > 0
