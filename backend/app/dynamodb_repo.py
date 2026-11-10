"""DynamoDB repository.

Table layout (created by Terraform, not by this process):
- pk / sk
- gsi1 listings-by-time: gsi1pk = LISTING, gsi1sk = created_at#id
- gsi2 listings-by-category: gsi2pk = CATEGORY#name, gsi2sk = created_at#id
- gsi3 listings-by-owner: gsi3pk = OWNER#id, gsi3sk = created_at#id
- gsi4 users-by-email: gsi4pk = EMAIL#email, gsi4sk = USER

Text search is applied after the query. A search engine is not part of this
project. This class never writes to SQLite if a call fails.
"""

from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import BotoCoreError, ClientError

from app.aws_session import provider_error
from app.errors import AppError
from app.sqlite_repo import filter_listings, new_id, utc_now


def user_id_from_email_index_item(item: dict) -> str:
    """Read the user id from a users-by-email hit.

    KEYS_ONLY indexes still return the table key. The id attribute is present
    only when the index projection includes it.
    """
    user_id = item.get("id")
    if isinstance(user_id, str) and user_id:
        return user_id
    pk = str(item.get("pk", ""))
    prefix = "USER#"
    if pk.startswith(prefix) and len(pk) > len(prefix):
        return pk[len(prefix):]
    raise AppError("The users-by-email index item did not include a user id.", 502)


class DynamoRepository:
    backend = "dynamodb"

    def __init__(self, table):
        self.table = table

    def prepare(self) -> None:
        return None

    def clear(self) -> None:
        raise RuntimeError("Refusing to bulk-delete a DynamoDB table from the test helper.")

    def create_user(self, *, email: str, name: str, password_hash: str | None, campus: str, bio: str = "") -> dict:
        user_id = new_id()
        created_at = utc_now()
        email_key = f"EMAIL#{email.lower()}"
        try:
            self.table.put_item(
                Item={"pk": email_key, "sk": "LOCK", "entity": "email-lock", "user_id": user_id},
                ConditionExpression=Attr("pk").not_exists(),
            )
            self.table.put_item(
                Item={
                    "pk": f"USER#{user_id}",
                    "sk": "PROFILE",
                    "entity": "user",
                    "id": user_id,
                    "email": email.lower(),
                    "name": name.strip(),
                    "password_hash": password_hash or "",
                    "campus": campus.strip(),
                    "bio": bio,
                    "created_at": created_at,
                    "gsi4pk": email_key,
                    "gsi4sk": "USER",
                }
            )
        except self.table.meta.client.exceptions.ConditionalCheckFailedException as exc:
            raise AppError("An account with that email already exists.", 409) from exc
        except (ClientError, BotoCoreError) as exc:
            raise provider_error("Amazon DynamoDB", exc) from exc
        return self._user_from_item(self.table.get_item(Key={"pk": f"USER#{user_id}", "sk": "PROFILE"})["Item"])

    def get_user_by_id(self, user_id: str) -> dict | None:
        try:
            item = self.table.get_item(Key={"pk": f"USER#{user_id}", "sk": "PROFILE"}).get("Item")
        except (ClientError, BotoCoreError) as exc:
            raise provider_error("Amazon DynamoDB", exc) from exc
        return self._user_from_item(item) if item else None

    def get_user_by_email(self, email: str) -> dict | None:
        try:
            items = self._collect(
                IndexName="users-by-email",
                KeyConditionExpression=Key("gsi4pk").eq(f"EMAIL#{email.lower()}") & Key("gsi4sk").eq("USER"),
            )
        except (ClientError, BotoCoreError) as exc:
            raise provider_error("Amazon DynamoDB", exc) from exc
        if not items:
            return None
        user_id = user_id_from_email_index_item(items[0])
        try:
            item = self.table.get_item(Key={"pk": f"USER#{user_id}", "sk": "PROFILE"}).get("Item")
        except (ClientError, BotoCoreError) as exc:
            raise provider_error("Amazon DynamoDB", exc) from exc
        if not item:
            return None
        full = self._user_from_item(item)
        full["password_hash"] = item.get("password_hash") or None
        return full

    def update_user(self, user_id: str, changes: dict) -> dict | None:
        current = self.get_user_by_id(user_id)
        if not current:
            return None
        current.update({key: value for key, value in changes.items() if value is not None})
        email_item = self.get_user_by_email(current["email"])
        password_hash = (email_item or {}).get("password_hash") or ""
        try:
            self.table.put_item(
                Item={
                    "pk": f"USER#{user_id}",
                    "sk": "PROFILE",
                    "entity": "user",
                    "id": user_id,
                    "email": current["email"],
                    "name": current["name"],
                    "password_hash": password_hash,
                    "campus": current["campus"],
                    "bio": current["bio"],
                    "created_at": self._as_text(current["created_at"]),
                    "gsi4pk": f"EMAIL#{current['email']}",
                    "gsi4sk": "USER",
                }
            )
        except (ClientError, BotoCoreError) as exc:
            raise provider_error("Amazon DynamoDB", exc) from exc
        return self.get_user_by_id(user_id)

    def upsert_identity(self, *, user_id: str, email: str, name: str) -> dict:
        existing = self.get_user_by_id(user_id)
        if existing:
            return existing
        by_email = self.get_user_by_email(email)
        if by_email:
            return {key: value for key, value in by_email.items() if key != "password_hash"}
        return self._put_identity(user_id=user_id, email=email, name=name)

    def add_upload(self, *, image_key: str, owner_id: str) -> dict:
        record = {"image_key": image_key, "owner_id": owner_id, "created_at": utc_now()}
        try:
            self.table.put_item(
                Item={
                    "pk": f"UPLOAD#{image_key}",
                    "sk": "META",
                    "entity": "upload",
                    **record,
                }
            )
        except (ClientError, BotoCoreError) as exc:
            raise provider_error("Amazon DynamoDB", exc) from exc
        return record

    def get_upload(self, image_key: str) -> dict | None:
        try:
            item = self.table.get_item(Key={"pk": f"UPLOAD#{image_key}", "sk": "META"}).get("Item")
        except (ClientError, BotoCoreError) as exc:
            raise provider_error("Amazon DynamoDB", exc) from exc
        if not item:
            return None
        return {"image_key": item["image_key"], "owner_id": item["owner_id"], "created_at": item["created_at"]}

    def delete_upload(self, image_key: str) -> None:
        try:
            self.table.delete_item(Key={"pk": f"UPLOAD#{image_key}", "sk": "META"})
        except (ClientError, BotoCoreError) as exc:
            raise provider_error("Amazon DynamoDB", exc) from exc

    def create_listing(self, listing: dict) -> dict:
        try:
            self.table.put_item(Item=self._listing_item(listing))
        except (ClientError, BotoCoreError) as exc:
            raise provider_error("Amazon DynamoDB", exc) from exc
        return listing

    def get_listing(self, listing_id: str) -> dict | None:
        try:
            item = self.table.get_item(Key={"pk": f"LISTING#{listing_id}", "sk": "META"}).get("Item")
        except (ClientError, BotoCoreError) as exc:
            raise provider_error("Amazon DynamoDB", exc) from exc
        return self._listing_from_item(item) if item else None

    def update_listing(self, listing: dict) -> dict:
        return self.create_listing(listing)

    def delete_listing(self, listing_id: str) -> None:
        try:
            self.table.delete_item(Key={"pk": f"LISTING#{listing_id}", "sk": "META"})
        except (ClientError, BotoCoreError) as exc:
            raise provider_error("Amazon DynamoDB", exc) from exc

    def list_listings(self, *, q: str = "", category: str = "", owner_id: str = "", intent: str = "") -> list[dict]:
        try:
            if owner_id:
                items = self._collect(
                    IndexName="listings-by-owner",
                    KeyConditionExpression=Key("gsi3pk").eq(f"OWNER#{owner_id}"),
                )
            elif category:
                items = self._collect(
                    IndexName="listings-by-category",
                    KeyConditionExpression=Key("gsi2pk").eq(f"CATEGORY#{category}"),
                )
            else:
                items = self._collect(
                    IndexName="listings-by-time",
                    KeyConditionExpression=Key("gsi1pk").eq("LISTING"),
                )
        except (ClientError, BotoCoreError) as exc:
            raise provider_error("Amazon DynamoDB", exc) from exc
        listings = [self._listing_from_item(item) for item in items if item.get("entity") == "listing"]
        return filter_listings(listings, q=q, category=category, owner_id=owner_id, intent=intent)

    def add_notification(self, *, user_id: str, message: str, channel: str) -> dict:
        created_at = utc_now()
        notification_id = new_id()
        record = {
            "id": notification_id,
            "user_id": user_id,
            "message": message,
            "channel": channel,
            "read": False,
            "created_at": created_at,
        }
        try:
            self.table.put_item(
                Item={
                    "pk": f"USER#{user_id}",
                    "sk": f"NOTIF#{created_at}#{notification_id}",
                    "entity": "notification",
                    **record,
                }
            )
        except (ClientError, BotoCoreError) as exc:
            raise provider_error("Amazon DynamoDB", exc) from exc
        return record

    def list_notifications(self, user_id: str) -> list[dict]:
        try:
            items = self._collect(
                KeyConditionExpression=Key("pk").eq(f"USER#{user_id}") & Key("sk").begins_with("NOTIF#"),
            )
        except (ClientError, BotoCoreError) as exc:
            raise provider_error("Amazon DynamoDB", exc) from exc
        notifications = [self._notification_from_item(item) for item in items]
        notifications.sort(key=lambda item: item["created_at"], reverse=True)
        return notifications[:50]

    def mark_notification_read(self, *, user_id: str, notification_id: str) -> dict | None:
        matches = [item for item in self.list_notifications(user_id) if item["id"] == notification_id]
        if not matches:
            return None
        current = matches[0]
        current["read"] = True
        try:
            self.table.update_item(
                Key={"pk": f"USER#{user_id}", "sk": f"NOTIF#{current['created_at']}#{notification_id}"},
                UpdateExpression="SET #read = :read",
                ExpressionAttributeNames={"#read": "read"},
                ExpressionAttributeValues={":read": True},
            )
        except (ClientError, BotoCoreError) as exc:
            raise provider_error("Amazon DynamoDB", exc) from exc
        return current

    def _put_identity(self, *, user_id: str, email: str, name: str) -> dict:
        created_at = utc_now()
        email_key = f"EMAIL#{email.lower()}"
        try:
            self.table.put_item(Item={"pk": email_key, "sk": "LOCK", "entity": "email-lock", "user_id": user_id})
            self.table.put_item(
                Item={
                    "pk": f"USER#{user_id}",
                    "sk": "PROFILE",
                    "entity": "user",
                    "id": user_id,
                    "email": email.lower(),
                    "name": name.strip() or email,
                    "password_hash": "",
                    "campus": "",
                    "bio": "",
                    "created_at": created_at,
                    "gsi4pk": email_key,
                    "gsi4sk": "USER",
                }
            )
        except (ClientError, BotoCoreError) as exc:
            raise provider_error("Amazon DynamoDB", exc) from exc
        return self.get_user_by_id(user_id)

    def _collect(self, **kwargs) -> list[dict]:
        items: list[dict] = []
        query = dict(kwargs)
        query["ScanIndexForward"] = False
        while len(items) < 200:
            response = self.table.query(**query)
            items.extend(response.get("Items", []))
            last = response.get("LastEvaluatedKey")
            if not last:
                break
            query["ExclusiveStartKey"] = last
        return items

    def _listing_item(self, listing: dict) -> dict:
        created_at = self._as_text(listing["created_at"])
        sort_key = f"{created_at}#{listing['id']}"
        return {
            "pk": f"LISTING#{listing['id']}",
            "sk": "META",
            "entity": "listing",
            "id": listing["id"],
            "owner_id": listing["owner_id"],
            "owner_name": listing["owner_name"],
            "title": listing["title"],
            "description": listing["description"],
            "category": listing["category"],
            "intent": listing["intent"],
            "location": listing["location"],
            "contact": listing["contact"],
            "image_key": listing.get("image_key") or "",
            "status": listing["status"],
            "description_source": listing["description_source"],
            "category_source": listing["category_source"],
            "created_at": created_at,
            "updated_at": self._as_text(listing["updated_at"]),
            "gsi1pk": "LISTING",
            "gsi1sk": sort_key,
            "gsi2pk": f"CATEGORY#{listing['category']}",
            "gsi2sk": sort_key,
            "gsi3pk": f"OWNER#{listing['owner_id']}",
            "gsi3sk": sort_key,
        }

    def _listing_from_item(self, item: dict) -> dict:
        image_key = item.get("image_key") or None
        return {
            "id": item["id"],
            "owner_id": item["owner_id"],
            "owner_name": item["owner_name"],
            "title": item["title"],
            "description": item["description"],
            "category": item["category"],
            "intent": item["intent"],
            "location": item.get("location", ""),
            "contact": item.get("contact", ""),
            "image_key": image_key,
            "status": item["status"],
            "description_source": item.get("description_source", "user"),
            "category_source": item.get("category_source", "user"),
            "created_at": item["created_at"],
            "updated_at": item["updated_at"],
        }

    def _user_from_item(self, item: dict) -> dict:
        return {
            "id": item["id"],
            "email": item["email"],
            "name": item["name"],
            "campus": item.get("campus", ""),
            "bio": item.get("bio", ""),
            "created_at": item["created_at"],
        }

    def _notification_from_item(self, item: dict) -> dict:
        return {
            "id": item["id"],
            "user_id": item["user_id"],
            "message": item["message"],
            "channel": item["channel"],
            "read": bool(item.get("read", False)),
            "created_at": self._as_text(item["created_at"]),
        }

    def _as_text(self, value) -> str:
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)
