"""
TWSE API - FastAPI Application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import chip

app = FastAPI(
    title="TWSE API",
    description="REST API service for fetching TWSE (Taiwan Stock Exchange) chip data",
    version="0.1.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chip.router, prefix="/api/v1/chip", tags=["chip"])


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "ok", "service": "twse-api"}


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}
