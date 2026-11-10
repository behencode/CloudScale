"""SQS-triggered listing image processor.

The Lambda runtime supplies boto3. Pillow must be included in the deployment
package; this source archive does not vendor it. A missing Pillow install
fails the batch item so the message can be retried and then sent to the DLQ.
"""

import json
import logging
import os

from imaging import thumbnail_bytes

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_clients: dict = {}


def _s3():
    if "s3" not in _clients:
        import boto3

        _clients["s3"] = boto3.client("s3")
    return _clients["s3"]


def _sns():
    if "sns" not in _clients:
        import boto3

        _clients["sns"] = boto3.client("sns")
    return _clients["sns"]


def _table():
    table_name = os.environ.get("DYNAMODB_TABLE", "")
    if not table_name:
        return None
    if "table" not in _clients:
        import boto3

        _clients["table"] = boto3.resource("dynamodb").Table(table_name)
    return _clients["table"]


def process_image(*, s3, table, bucket: str, listing_id: str, image_key: str) -> str:
    response = s3.get_object(Bucket=bucket, Key=image_key)
    body = response["Body"]
    try:
        data = body.read()
    finally:
        body.close()
    thumbnail = thumbnail_bytes(data)
    destination = f"processed/{listing_id}.jpg"
    s3.put_object(Bucket=bucket, Key=destination, Body=thumbnail, ContentType="image/jpeg")
    if table is not None:
        table.update_item(
            Key={"pk": f"LISTING#{listing_id}", "sk": "META"},
            UpdateExpression="SET image_key = :image_key",
            ExpressionAttributeValues={":image_key": destination},
        )
    return destination


def handler(event, context, s3=None, sns=None, table=None):
    bucket = os.environ.get("S3_BUCKET", "")
    topic_arn = os.environ.get("SNS_TOPIC_ARN", "")
    s3_client = s3 if s3 is not None else _s3()
    sns_client = sns if sns is not None else (_sns() if topic_arn else None)
    table_resource = table if table is not None else _table()
    failures = []
    for record in event.get("Records", []):
        message_id = record.get("messageId", "")
        try:
            payload = json.loads(record.get("body") or "{}")
            if payload.get("job") != "process-image":
                logger.info("Skipping message %s with job %s", message_id, payload.get("job"))
                continue
            listing_id = payload["listing_id"]
            image_key = payload["image_key"]
            if not bucket:
                raise RuntimeError("S3_BUCKET is not configured.")
            destination = process_image(
                s3=s3_client,
                table=table_resource,
                bucket=bucket,
                listing_id=listing_id,
                image_key=image_key,
            )
            if sns_client is not None and topic_arn:
                sns_client.publish(
                    TopicArn=topic_arn,
                    Subject="CampusConnect image processed",
                    Message=json.dumps(
                        {
                            "job": "process-image",
                            "listing_id": listing_id,
                            "image_key": destination,
                        }
                    ),
                )
        except Exception:
            logger.exception("Image processing failed for message %s", message_id)
            if message_id:
                failures.append({"itemIdentifier": message_id})
    return {"batchItemFailures": failures}
