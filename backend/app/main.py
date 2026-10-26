from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.emergencies import router as emergency_router
from app.api.community import router as community_router
from app.api.assistant import router as assistant_router
from app.api.messaging import router as messaging_router
from app.api.routes import router
from app.core.config import settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.app_env == "production" and settings.jwt_secret == "development-only-change-this-secret":
        raise RuntimeError("JWT_SECRET must be configured in production")
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(router)
app.include_router(emergency_router)
app.include_router(messaging_router)
app.include_router(community_router)
app.include_router(assistant_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
