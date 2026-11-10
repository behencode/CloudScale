"""Adapter tests.

Fake clients here exercise request construction. They are not used by the running
application, and the application does not swap them in when AWS is selected.
"""

import io
import json

import pytest
from botocore.exceptions import ClientError
from PIL import Image

from app.ai import (
    BedrockDescriptionService,
    LocalCategoryService,
    SageMakerCategoryService,
    _category_from_payload,
)
from app.config import Settings
from app.dynamodb_repo import DynamoRepository, user_id_from_email_index_item
from app.errors import ProviderError
from app.notify import AwsNotifier
from app.repositories import repository_method_names
from app.sqlite_repo import SqliteRepository


def test_repository_public_methods_match():
    sqlite_names, dynamo_names = repository_method_names()
    assert sqlite_names == dynamo_names


def test_email_lookup_reads_password_from_profile_item():
    class Table:
        def __init__(self):
            self.profile = {
                "pk": "USER#user1",
                "sk": "PROFILE",
                "id": "user1",
                "email": "ada@campus.edu",
                "name": "Ada",
                "campus": "North",
                "bio": "",
                "created_at": "2026-11-11T12:00:00+00:00",
                "password_hash": "stored-hash",
            }

        def get_item(self, Key):
            if Key == {"pk": "USER#user1", "sk": "PROFILE"}:
                return {"Item": self.profile}
            return {}

        def query(self, **_kwargs):
            return {
                "Items": [
                    {
                        "pk": "USER#user1",
                        "sk": "PROFILE",
                        "gsi4pk": "EMAIL#ada@campus.edu",
                        "gsi4sk": "USER",
                    }
                ]
            }

    user = DynamoRepository(Table()).get_user_by_email("Ada@campus.edu")
    assert user["id"] == "user1"
    assert user["password_hash"] == "stored-hash"
    assert user_id_from_email_index_item({"pk": "USER#abc", "sk": "PROFILE"}) == "abc"


def test_listing_item_uses_access_pattern_keys():
    listing = {
        "id": "abc123",
        "owner_id": "user1",
        "owner_name": "Ada",
        "title": "Lamp",
        "description": "A working desk lamp for a dorm room.",
        "category": "community",
        "intent": "offer",
        "location": "Dorm A",
        "contact": "ada@campus.edu",
        "image_key": None,
        "status": "open",
        "description_source": "user",
        "category_source": "user",
        "created_at": "2026-11-11T12:00:00+00:00",
        "updated_at": "2026-11-11T12:00:00+00:00",
    }
    item = DynamoRepository(table=object())._listing_item(listing)
    assert item["pk"] == "LISTING#abc123"
    assert item["sk"] == "META"
    assert item["gsi1pk"] == "LISTING"
    assert item["gsi2pk"] == "CATEGORY#community"
    assert item["gsi3pk"] == "OWNER#user1"
    assert item["image_key"] == ""


def test_bedrock_converse_sets_max_tokens():
    captured = {}

    class FakeBedrock:
        def converse(self, **kwargs):
            captured.update(kwargs)
            return {"output": {"message": {"content": [{"text": "A spare lamp for a dorm desk."}]}}}

    result = BedrockDescriptionService(FakeBedrock(), "us.amazon.nova-micro-v1:0", 256).generate(
        title="Desk lamp",
        category="community",
        details="Works",
    )
    assert captured["modelId"] == "us.amazon.nova-micro-v1:0"
    assert captured["inferenceConfig"]["maxTokens"] == 256
    assert result["provider"] == "amazon-bedrock"
    assert "can incur charges" in result["notice"]
    assert "Desk lamp" in captured["messages"][0]["content"][0]["text"]


def test_sagemaker_rejects_unknown_shape():
    class FakeRuntime:
        def invoke_endpoint(self, **_kwargs):
            class Body:
                def read(self):
                    return json.dumps({"scores": [0.2, 0.8]}).encode()

                def close(self):
                    return None

            return {"Body": Body()}

    with pytest.raises(ProviderError, match="category"):
        SageMakerCategoryService(FakeRuntime(), "campusconnect-category").predict(title="Lamp", details="")


def test_sagemaker_accepts_predicted_label():
    class FakeRuntime:
        def invoke_endpoint(self, **kwargs):
            assert kwargs["EndpointName"] == "campusconnect-category"
            assert kwargs["ContentType"] == "application/json"
            assert json.loads(kwargs["Body"].decode())["title"] == "Room to sublet"

            class Body:
                def read(self):
                    return json.dumps({"predicted_label": "housing", "confidence": 0.91}).encode()

                def close(self):
                    return None

            return {"Body": Body()}

    result = SageMakerCategoryService(FakeRuntime(), "campusconnect-category").predict(
        title="Room to sublet",
        details="Available in May",
    )
    assert result["category"] == "housing"
    assert result["provider"] == "amazon-sagemaker"
    assert result["confidence"] == 0.91


def test_category_payload_helper_reads_label():
    assert _category_from_payload({"label": "Events"}) == "events"


def test_local_classifier_covers_required_categories():
    service = LocalCategoryService()
    assert service.predict(title="Lost wallet", details="")["category"] == "lost-and-found"
    assert service.predict(title="Concert ticket", details="")["category"] == "events"
    assert service.predict(title="Volunteer club tutoring", details="")["category"] == "community"


def test_aws_notifier_publishes_before_recording(tmp_path):
    repo = SqliteRepository(str(tmp_path / "notes.db"))
    repo.prepare()
    user = repo.create_user(email="ada@campus.edu", name="Ada", password_hash="x", campus="")
    calls = []

    class SQS:
        def send_message(self, **kwargs):
            calls.append(("sqs", kwargs))

    class SNS:
        def publish(self, **kwargs):
            calls.append(("sns", kwargs))

    notifier = AwsNotifier(repo, SQS(), SNS(), "https://sqs.example/queue", "arn:aws:sns:us-east-1:1:topic")
    listing = {
        "id": "listing1",
        "title": "Lamp",
        "image_key": "uploads/user/file.jpg",
    }
    note = notifier.listing_published(user, listing)
    assert [name for name, _payload in calls] == ["sqs", "sns"]
    assert json.loads(calls[0][1]["MessageBody"])["job"] == "process-image"
    assert note["channel"] == "amazon-sns"
    assert repo.list_notifications(user["id"])[0]["id"] == note["id"]


def test_aws_notifier_does_not_record_success_when_sqs_fails(tmp_path):
    repo = SqliteRepository(str(tmp_path / "notes.db"))
    repo.prepare()
    user = repo.create_user(email="ada@campus.edu", name="Ada", password_hash="x", campus="")

    class SQS:
        def send_message(self, **_kwargs):
            raise ClientError({"Error": {"Code": "AccessDenied", "Message": "denied"}}, "SendMessage")

    class SNS:
        def publish(self, **_kwargs):
            raise AssertionError("SNS should not be called after SQS fails")

    notifier = AwsNotifier(repo, SQS(), SNS(), "https://sqs.example/queue", "arn:aws:sns:us-east-1:1:topic")
    with pytest.raises(ProviderError, match="AccessDenied"):
        notifier.listing_published(user, {"id": "listing1", "title": "Lamp", "image_key": "uploads/u/a.jpg"})
    assert repo.list_notifications(user["id"]) == []


def test_settings_warn_about_real_aws_calls_in_local_mode():
    settings = Settings(
        app_mode="local",
        description_provider="bedrock",
        jwt_secret="not-the-default",
    )
    warnings = settings.configuration_warnings()
    assert any("descriptions" in warning for warning in warnings)


def test_thumbnail_writes_jpeg():
    from app.images import thumbnail_bytes

    buffer = io.BytesIO()
    Image.new("RGB", (1600, 400), (10, 20, 30)).save(buffer, format="PNG")
    result = thumbnail_bytes(buffer.getvalue(), max_edge=128)
    image = Image.open(io.BytesIO(result))
    assert image.format == "JPEG"
    assert max(image.size) <= 128
