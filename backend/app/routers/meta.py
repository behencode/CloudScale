from fastapi import APIRouter, Request

from app.schemas import HealthOut

router = APIRouter(prefix="/api", tags=["Meta"])


@router.get("/health", response_model=HealthOut)
def health(request: Request):
    settings = request.app.state.settings
    return HealthOut(
        status="ok",
        service="campusconnect",
        app_mode=settings.app_mode,
        auth_mode=settings.auth_mode,
        database_backend=settings.database_backend,
        storage_backend=settings.storage_backend,
        description_provider=settings.description_provider,
        category_provider=settings.category_provider,
        notification_backend=settings.notification_backend,
        warnings=settings.configuration_warnings(),
    )
