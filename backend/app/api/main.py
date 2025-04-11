from fastapi import APIRouter

from app.api.routes import (
    items, login, private, users, utils,
    profiles, nutritionists, availability, appointments, nutrition_records
)
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(items.router)
api_router.include_router(profiles.router, prefix="/profiles")
api_router.include_router(nutritionists.router, prefix="/nutritionists")
api_router.include_router(availability.router, prefix="/availability")
api_router.include_router(appointments.router, prefix="/appointments")
api_router.include_router(nutrition_records.router, prefix="/nutrition-records")

if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)