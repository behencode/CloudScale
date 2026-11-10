"""File storage. S3 methods perform real API calls and do not fall back locally."""

import io
import re
import uuid
from pathlib import Path

from botocore.exceptions import BotoCoreError, ClientError

from app.aws_session import provider_error
from app.errors import AppError

_LOCAL_KEY = re.compile(r"^[a-f0-9]{32}\.jpg$")
_S3_KEY = re.compile(r"^(uploads|processed)/[A-Za-z0-9._/-]{1,400}\.jpg$")


class LocalStorage:
    kind = "local"

    def __init__(self, upload_dir: str):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def save(self, owner_id: str, data: bytes, content_type: str) -> str:
        del owner_id, content_type
        key = f"{uuid.uuid4().hex}.jpg"
        target = self.upload_dir / key
        target.write_bytes(data)
        return key

    def url_for(self, key: str | None) -> str | None:
        if not key:
            return None
        if not _LOCAL_KEY.fullmatch(key):
            raise AppError("Image key is not valid.", 400)
        return f"/uploads/{key}"

    def open_bytes(self, key: str) -> bytes:
        if not _LOCAL_KEY.fullmatch(key):
            raise AppError("Image key is not valid.", 400)
        path = self.upload_dir / key
        if not path.is_file():
            raise AppError("Image file was not found.", 404)
        return path.read_bytes()

    def delete(self, key: str | None) -> None:
        if not key:
            return
        if not _LOCAL_KEY.fullmatch(key):
            raise AppError("Image key is not valid.", 400)
        path = self.upload_dir / key
        if path.is_file():
            path.unlink()


class S3Storage:
    kind = "s3"

    def __init__(self, client, bucket: str):
        if not bucket:
            raise AppError("S3_BUCKET is required when STORAGE_BACKEND=s3.", 503)
        self.client = client
        self.bucket = bucket

    def save(self, owner_id: str, data: bytes, content_type: str) -> str:
        key = f"uploads/{owner_id}/{uuid.uuid4().hex}.jpg"
        try:
            self.client.upload_fileobj(
                io.BytesIO(data),
                self.bucket,
                key,
                ExtraArgs={"ContentType": content_type},
            )
        except (ClientError, BotoCoreError) as exc:
            raise provider_error("Amazon S3", exc) from exc
        return key

    def url_for(self, key: str | None) -> str | None:
        if not key:
            return None
        if not _S3_KEY.fullmatch(key):
            raise AppError("Image key is not valid.", 400)
        try:
            return self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=3600,
            )
        except (ClientError, BotoCoreError) as exc:
            raise provider_error("Amazon S3", exc) from exc

    def open_bytes(self, key: str) -> bytes:
        if not _S3_KEY.fullmatch(key):
            raise AppError("Image key is not valid.", 400)
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            body = response["Body"]
            try:
                return body.read()
            finally:
                body.close()
        except (ClientError, BotoCoreError) as exc:
            raise provider_error("Amazon S3", exc) from exc

    def delete(self, key: str | None) -> None:
        if not key:
            return
        if not _S3_KEY.fullmatch(key):
            raise AppError("Image key is not valid.", 400)
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
        except (ClientError, BotoCoreError) as exc:
            raise provider_error("Amazon S3", exc) from exc


def build_storage(settings):
    if settings.storage_backend == "local":
        return LocalStorage(settings.upload_dir)
    if settings.storage_backend == "s3":
        from app.aws_session import aws_config, aws_session

        client = aws_session(settings).client("s3", config=aws_config())
        return S3Storage(client, settings.s3_bucket)
    raise AppError(f"Unknown storage backend: {settings.storage_backend}", 503)
