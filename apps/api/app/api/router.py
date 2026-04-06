from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.closet import router as closet_router
from app.api.routes.health import router as health_router
from app.api.routes.outfits import router as outfits_router
from app.api.routes.profile import router as profile_router
from app.api.routes.wear import router as wear_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(profile_router)
api_router.include_router(closet_router)
api_router.include_router(outfits_router)
api_router.include_router(wear_router)
