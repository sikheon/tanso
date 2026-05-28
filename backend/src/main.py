"""FastAPI application entrypoint."""

from src.core import asyncio_compat  # noqa: F401  — Windows psycopg async fix

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src import __version__
from src.api.health import router as health_router
from src.api.routers.emission_factors import router as emission_factors_router
from src.api.routers.geocode import router as geocode_router
from src.api.routers.p2p import router as p2p_router
from src.api.routers.parse import router as parse_router
from src.api.routers.runs import router as runs_router
from src.api.routers.stats import router as stats_router
from src.api.routers.vehicles import router as vehicles_router
from src.api.routers.vrp import router as vrp_router
from src.core.config import get_settings
from src.core.logging import configure_logging, get_logger

settings = get_settings()
configure_logging(level=settings.log_level, json_format=settings.log_format == "json")
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("elo.startup", version=__version__, model=settings.gemini_model)
    yield
    log.info("elo.shutdown")


app = FastAPI(
    title="E.L.O — Eco Logistics Optimizer",
    description="LLM-driven multi-engine routing with CO₂ optimization",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(health_router)
app.include_router(vehicles_router)
app.include_router(runs_router)
app.include_router(p2p_router)
app.include_router(vrp_router)
app.include_router(parse_router)
app.include_router(stats_router)
app.include_router(emission_factors_router)
app.include_router(geocode_router)


@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    return {
        "name": "E.L.O",
        "description": "Eco Logistics Optimizer",
        "version": __version__,
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=False,
        loop="asyncio",  # forces uvicorn to use the SelectorEventLoopPolicy our shim installed
    )
