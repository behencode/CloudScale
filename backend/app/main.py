from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.ai import build_category_service, build_description_service
from app.config import get_settings
from app.errors import AppError
from app.notify import build_notifier
from app.repositories import build_repository
from app.routers import auth, listings, meta
from app.storage import build_storage


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    Path(settings.sqlite_path).parent.mkdir(parents=True, exist_ok=True)
    repo = build_repository(settings)
    storage = build_storage(settings)
    app.state.settings = settings
    app.state.repo = repo
    app.state.storage = storage
    app.state.notifier = build_notifier(settings, repo)
    app.state.description_service = build_description_service(settings)
    app.state.category_service = build_category_service(settings)
    yield


app = FastAPI(
    title="CampusConnect",
    version="1.0.0",
    summary="University community resource sharing for the CloudScale project.",
    description=(
        "Local development uses SQLite, filesystem images, a labelled local password login, "
        "a template description writer, and a keyword category classifier. "
        "Amazon Bedrock, SageMaker, DynamoDB, S3, Cognito, SQS, SNS, and Lambda run only when "
        "the matching configuration value is selected. Failures from those services are returned "
        "as errors and are not replaced with local results."
    ),
    lifespan=lifespan,
)


@app.exception_handler(AppError)
async def handle_app_error(_request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


def _mount_uploads() -> None:
    settings = get_settings()
    directory = Path(settings.upload_dir)
    directory.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(directory)), name="uploads")


def _install_cors() -> None:
    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


_install_cors()
app.include_router(meta.router)
app.include_router(auth.router)
app.include_router(listings.router)
_mount_uploads()


@app.get("/", tags=["Meta"])
def root():
    return {"service": "campusconnect", "docs": "/docs", "health": "/api/health"}
