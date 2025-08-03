from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.core.database import connect_to_mongo, close_mongo_connection
from app.api.v1.router import api_router
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # On startup
    await connect_to_mongo()
    yield
    # On shutdown
    await close_mongo_connection()


app = FastAPI(
    title="Optical Network Topology Management API",
    description="This API provides endpoints to manage optical network topologies.",
    version="1.0.0",
    lifespan=lifespan
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有源（生产环境应改为具体域名）
    allow_credentials=True,  # 允许携带凭证（如 cookies）
    allow_methods=["*"],  # 允许所有方法（GET, POST, PUT 等）
    allow_headers=["*"],  # 允许所有头部
)


@app.get("/", tags=["Root"])
async def read_root():
    return {"message": "Welcome to the Optical Network Topology Management API"}


# Include the version 1 API router
app.include_router(api_router, prefix="/api/v1")
