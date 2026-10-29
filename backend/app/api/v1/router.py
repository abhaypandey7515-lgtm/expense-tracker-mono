"""API v1 router: authentication, groups, expenses."""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, expenses, groups

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(groups.router)
api_router.include_router(expenses.router)
