import io
import json
import sys
from pathlib import Path

from PIL import Image

PROCESSOR = Path(__file__).resolve().parents[1] / "lambda" / "image_processor"
sys.path.insert(0, str(PROCESSOR))

from handler import handler  # noqa: E402


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (40, 20), (200, 40, 40)).save(buffer, format="PNG")
    return buffer.getvalue()


class _Body:
    def __init__(self, data: bytes):
        self.data = data

    def read(self):
        return self.data

    def close(self):
        return None


class _S3:
    def __init__(self):
        self.puts = []

    def get_object(self, Bucket, Key):
        del Bucket, Key
        return {"Body": _Body(_png())}

    def put_object(self, **kwargs):
        self.puts.append(kwargs)


class _SNS:
    def __init__(self):
        self.messages = []

    def publish(self, **kwargs):
        self.messages.append(kwargs)


class _Table:
    def __init__(self):
        self.updates = []

    def update_item(self, **kwargs):
        self.updates.append(kwargs)


def test_handler_writes_thumbnail_and_reports_failures(monkeypatch):
    monkeypatch.setenv("S3_BUCKET", "campus-media")
    monkeypatch.setenv("SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:123456789012:notes")
    s3 = _S3()
    sns = _SNS()
    table = _Table()
    event = {
        "Records": [
            {
                "messageId": "ok-1",
                "body": json.dumps(
                    {"job": "process-image", "listing_id": "listing1", "image_key": "uploads/user/source.jpg"}
                ),
            },
            {"messageId": "skip-1", "body": json.dumps({"job": "other"})},
            {"messageId": "bad-1", "body": json.dumps({"job": "process-image"})},
        ]
    }
    result = handler(event, None, s3=s3, sns=sns, table=table)
    assert result["batchItemFailures"] == [{"itemIdentifier": "bad-1"}]
    assert s3.puts[0]["Key"] == "processed/listing1.jpg"
    assert s3.puts[0]["ContentType"] == "image/jpeg"
    assert table.updates[0]["Key"] == {"pk": "LISTING#listing1", "sk": "META"}
    assert json.loads(sns.messages[0]["Message"])["image_key"] == "processed/listing1.jpg"
