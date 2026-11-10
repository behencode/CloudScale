from datetime import datetime

from app.errors import AppError
from app.sqlite_repo import new_id, utc_now


def public_listing(listing: dict, storage) -> dict:
    data = dict(listing)
    data["image_url"] = storage.url_for(data.get("image_key"))
    for field in ("created_at", "updated_at"):
        value = data[field]
        if isinstance(value, str):
            data[field] = datetime.fromisoformat(value)
    return data


def require_owned_upload(repo, user: dict, image_key: str | None) -> None:
    if not image_key:
        return
    upload = repo.get_upload(image_key)
    if not upload or upload["owner_id"] != user["id"]:
        raise AppError("That image upload was not found for this account.", 400)


def build_listing(user: dict, payload) -> dict:
    timestamp = utc_now()
    return {
        "id": new_id(),
        "owner_id": user["id"],
        "owner_name": user["name"],
        "title": payload.title.strip(),
        "description": payload.description.strip(),
        "category": payload.category,
        "intent": payload.intent,
        "location": payload.location.strip(),
        "contact": payload.contact.strip(),
        "image_key": payload.image_key,
        "status": "open",
        "description_source": payload.description_source,
        "category_source": payload.category_source,
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def apply_listing_changes(listing: dict, payload) -> dict:
    changes = payload.model_dump(exclude_unset=True)
    clear_image = changes.pop("clear_image", False)
    image_key = changes.pop("image_key", None)
    for field, value in changes.items():
        if isinstance(value, str):
            value = value.strip()
        listing[field] = value
    if clear_image:
        listing["image_key"] = None
    elif image_key is not None:
        listing["image_key"] = image_key
    listing["updated_at"] = utc_now()
    return listing
