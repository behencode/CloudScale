"""Resize listing photos. Shared by the API and the image-processing Lambda."""

import io


def thumbnail_bytes(data: bytes, max_edge: int = 1280) -> bytes:
    from PIL import Image, UnidentifiedImageError

    if max_edge < 64:
        raise ValueError("max_edge must be at least 64.")
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Upload is not a readable image.") from exc
    if getattr(image, "is_animated", False):
        image.seek(0)
    image = image.convert("RGB")
    image.thumbnail((max_edge, max_edge))
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=85)
    return output.getvalue()
