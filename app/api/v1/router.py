# app/api/v1/router.py
from fastapi import APIRouter
from .endpoints import networks, elements, connections, services, global_settings, import_export,simulations

api_router = APIRouter()

# Include all endpoint routers here
api_router.include_router(networks.router, prefix="/networks", tags=["Network"])
api_router.include_router(elements.router, prefix="/networks/{network_id}/elements", tags=["Topology Elements"])
api_router.include_router(connections.router, prefix="/networks/{network_id}/connections", tags=["Topology Connections"])
api_router.include_router(services.router, prefix="/networks/{network_id}/services", tags=["Service Management"])
api_router.include_router(global_settings.router, prefix="/networks/{network_id}", tags=["Global Network Settings"])
api_router.include_router(import_export.router, prefix="/networks", tags=["Import/Export"]) # Note: /networks/import is a top-level route
api_router.include_router(simulations.router, prefix="/simulations", tags=["Simulations"])
