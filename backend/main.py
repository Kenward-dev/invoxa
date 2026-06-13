"""Application entrypoint and FastAPI app configuration."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.database import Base, engine
from app.core.exceptions import AppError

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables when the API process starts."""
    with engine.begin() as conn:
        Base.metadata.create_all(bind=conn)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def invoicio_exception_handler(request: Request, exc: AppError) -> JSONResponse:
    """Convert application exceptions into JSON API responses."""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


uploads_path = settings.uploads_path
app.mount("/uploads", StaticFiles(directory=str(uploads_path)), name="uploads")


@app.get("/api/health")
async def health() -> dict:
    """Return a small readiness response for health checks."""
    return {"status": "ok", "version": settings.APP_VERSION}
