from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, UploadFile

from app.errors import AppError
from app.images import thumbnail_bytes
from app.listings import apply_listing_changes, build_listing, public_listing, require_owned_upload
from app.routers.auth import optional_user, require_user
from app.schemas import (
    CategoryIn,
    CategoryOut,
    DescriptionIn,
    DescriptionOut,
    ListingCreateOut,
    ListingIn,
    ListingOut,
    ListingUpdate,
    NotificationOut,
    UploadOut,
)

router = APIRouter(prefix="/api", tags=["Listings"])
MAX_IMAGE_BYTES = 5 * 1024 * 1024


def _owned_listing(request: Request, listing_id: str, user: dict) -> dict:
    listing = request.app.state.repo.get_listing(listing_id)
    if not listing:
        raise AppError("Listing was not found.", 404)
    if listing["owner_id"] != user["id"]:
        raise AppError("You can only change your own listings.", 403)
    return listing


@router.get("/categories")
def categories():
    from app.constants import CATEGORY_LABELS, INTENTS

    return {
        "categories": [{"id": key, "label": label} for key, label in CATEGORY_LABELS.items()],
        "intents": list(INTENTS),
    }


@router.get("/listings", response_model=list[ListingOut])
def list_listings(
    request: Request,
    q: str = "",
    category: str = "",
    intent: str = "",
    mine: bool = False,
    user: Annotated[dict | None, Depends(optional_user)] = None,
):
    owner_id = ""
    if mine:
        if not user:
            raise AppError("Sign in required.", 401)
        owner_id = user["id"]
    listings = request.app.state.repo.list_listings(q=q, category=category, owner_id=owner_id, intent=intent)
    return [public_listing(listing, request.app.state.storage) for listing in listings]


@router.get("/listings/{listing_id}", response_model=ListingOut)
def get_listing(listing_id: str, request: Request):
    listing = request.app.state.repo.get_listing(listing_id)
    if not listing:
        raise AppError("Listing was not found.", 404)
    return public_listing(listing, request.app.state.storage)


@router.post("/listings", response_model=ListingCreateOut, status_code=201)
def create_listing(body: ListingIn, request: Request, user: Annotated[dict, Depends(require_user)]):
    require_owned_upload(request.app.state.repo, user, body.image_key)
    listing = build_listing(user, body)
    request.app.state.repo.create_listing(listing)
    warning = None
    try:
        request.app.state.notifier.listing_published(user, listing)
    except AppError as exc:
        warning = exc.message
    return ListingCreateOut(listing=public_listing(listing, request.app.state.storage), notification_warning=warning)


@router.patch("/listings/{listing_id}", response_model=ListingOut)
def update_listing(
    listing_id: str,
    body: ListingUpdate,
    request: Request,
    user: Annotated[dict, Depends(require_user)],
):
    listing = _owned_listing(request, listing_id, user)
    old_image_key = listing.get("image_key")
    if body.image_key:
        require_owned_upload(request.app.state.repo, user, body.image_key)
    updated = apply_listing_changes(listing, body)
    request.app.state.repo.update_listing(updated)
    if old_image_key and old_image_key != updated.get("image_key"):
        request.app.state.storage.delete(old_image_key)
        request.app.state.repo.delete_upload(old_image_key)
    return public_listing(updated, request.app.state.storage)


@router.delete("/listings/{listing_id}", status_code=204)
def delete_listing(listing_id: str, request: Request, user: Annotated[dict, Depends(require_user)]):
    listing = _owned_listing(request, listing_id, user)
    image_key = listing.get("image_key")
    if image_key:
        request.app.state.storage.delete(image_key)
        request.app.state.repo.delete_upload(image_key)
    request.app.state.repo.delete_listing(listing_id)


@router.post("/uploads", response_model=UploadOut, tags=["Uploads"])
async def upload_image(
    request: Request,
    user: Annotated[dict, Depends(require_user)],
    file: UploadFile = File(...),
):
    data = await file.read()
    if not data:
        raise AppError("Choose an image file.", 400)
    if len(data) > MAX_IMAGE_BYTES:
        raise AppError("Images must be 5 MB or smaller.", 400)
    try:
        processed = thumbnail_bytes(data)
    except ValueError as exc:
        raise AppError(str(exc), 400) from exc
    image_key = request.app.state.storage.save(user["id"], processed, "image/jpeg")
    request.app.state.repo.add_upload(image_key=image_key, owner_id=user["id"])
    return UploadOut(image_key=image_key, image_url=request.app.state.storage.url_for(image_key))


@router.post("/listings/assist/description", response_model=DescriptionOut, tags=["Applied AI"])
def describe(body: DescriptionIn, request: Request, user: Annotated[dict, Depends(require_user)]):
    del user
    return request.app.state.description_service.generate(
        title=body.title,
        category=body.category,
        details=body.details,
    )


@router.post("/listings/assist/category", response_model=CategoryOut, tags=["Applied AI"])
def predict_category(body: CategoryIn, request: Request, user: Annotated[dict, Depends(require_user)]):
    del user
    return request.app.state.category_service.predict(title=body.title, details=body.details)


@router.get("/notifications", response_model=list[NotificationOut], tags=["Notifications"])
def notifications(request: Request, user: Annotated[dict, Depends(require_user)]):
    return request.app.state.repo.list_notifications(user["id"])


@router.post("/notifications/{notification_id}/read", response_model=NotificationOut, tags=["Notifications"])
def read_notification(
    notification_id: str,
    request: Request,
    user: Annotated[dict, Depends(require_user)],
):
    updated = request.app.state.repo.mark_notification_read(user_id=user["id"], notification_id=notification_id)
    if not updated:
        raise AppError("Notification was not found.", 404)
    return updated
