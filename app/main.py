"""TWSE API — FastAPI Application"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.connection import close_db, init_db
from app.routers import chip
from app.routers import margin


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()


app = FastAPI(
    title="TWSE API",
    description="REST API service for TWSE chip data with PostgreSQL caching",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chip.router, prefix="/api/v1/chip", tags=["chip"])
app.include_router(margin.router, prefix="/api/v1/margin", tags=["margin"])


@app.get("/")
async def root():
    return {"status": "ok", "service": "twse-api"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
