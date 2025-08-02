from fastapi import APIRouter
from .endpoints import networks

api_router = APIRouter()

# Include all endpoint routers here
api_router.include_router(networks.router, prefix="/networks", tags=["Networks"])
# api_router.include_router(elements.router, prefix="/networks/{network_id}/elements", tags=["Topology Elements"])
# api_router.include_router(connections.router, prefix="/networks/{network_id}/connections", tags=["Topology Connections"])
# api_router.include_router(services.router, prefix="/networks/{network_id}/services", tags=["Services"])
# api_router.include_router(settings.router, prefix="/networks/{network_id}", tags=["Global Settings"])
# api_router.include_router(import_export.router, tags=["Import/Export"])

# Note: The other routers need to be created similarly to networks.py
