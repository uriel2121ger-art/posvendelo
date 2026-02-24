"""
TITAN POS - Employees Microservice

Standalone FastAPI application for employee management.
First microservice extracted from the monolith (Phase 3).

Port: 8001
Tables owned: employees, employee_loans, loan_payments,
              attendance, time_clock_entries, breaks
"""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router as employees_router
from db.connection import check_db_health

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SERVICE_NAME = "employees-svc"
SERVICE_VERSION = "1.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info(f"Starting {SERVICE_NAME} v{SERVICE_VERSION}")
    healthy = await check_db_health()
    if healthy:
        logger.info("Database connection OK")
    else:
        logger.warning("Database connection failed - service may not work correctly")
    yield
    logger.info(f"Shutting down {SERVICE_NAME}")


app = FastAPI(
    title="TITAN POS - Employees Service",
    description="Employee management microservice for TITAN POS",
    version=SERVICE_VERSION,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(employees_router, prefix="/api/v1/employees", tags=["employees"])


@app.get("/health")
async def health_check():
    """Health check endpoint for Docker/Traefik."""
    db_healthy = await check_db_health()
    return {
        "status": "healthy" if db_healthy else "degraded",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "database": "connected" if db_healthy else "disconnected",
    }
