"""Expense Tracker backend: FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.session import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "Group expense tracker. Users register and log in, create or join a group with an invite "
        "code, record shared expenses, and settle up with the fewest payments.\n\n"
        "**Auth:** `POST /api/v1/auth/login` returns a bearer token; send it as "
        "`Authorization: Bearer <token>`. Every group route also checks group membership (403).\n\n"
        "**Money:** requests use decimal amounts (`\"450.50\"`); responses use integer minor units "
        "(`*_minor`, paise)."
    ),
    lifespan=lifespan,
)

if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy", "service": settings.PROJECT_NAME, "version": settings.VERSION}


app.include_router(api_router, prefix=settings.API_V1_STR)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
