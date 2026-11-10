"""Notification delivery.

Local mode writes an in-app notification and does not call SQS, SNS, or Lambda.
AWS mode writes the in-app record only after the SQS and SNS API calls succeed.
"""

import json

from botocore.exceptions import BotoCoreError, ClientError

from app.aws_session import aws_config, aws_session, provider_error
from app.errors import ConfigurationError


class LocalNotifier:
    backend = "local"

    def __init__(self, repo):
        self.repo = repo

    def listing_published(self, user: dict, listing: dict) -> dict:
        if listing.get("image_key"):
            message = (
                f"Your listing “{listing['title']}” was published. "
                "The photo was resized in the local API process. SQS, SNS, and Lambda were not called."
            )
        else:
            message = (
                f"Your listing “{listing['title']}” was published. "
                "SQS, SNS, and Lambda were not called."
            )
        return self.repo.add_notification(user_id=user["id"], message=message, channel="local-database")


class AwsNotifier:
    backend = "aws"

    def __init__(self, repo, sqs, sns, queue_url: str, topic_arn: str):
        if not queue_url or not topic_arn:
            raise ConfigurationError("SQS_QUEUE_URL and SNS_TOPIC_ARN are required when NOTIFICATION_BACKEND=aws.")
        self.repo = repo
        self.sqs = sqs
        self.sns = sns
        self.queue_url = queue_url
        self.topic_arn = topic_arn

    def listing_published(self, user: dict, listing: dict) -> dict:
        try:
            if listing.get("image_key"):
                self.sqs.send_message(
                    QueueUrl=self.queue_url,
                    MessageBody=json.dumps(
                        {
                            "job": "process-image",
                            "listing_id": listing["id"],
                            "image_key": listing["image_key"],
                            "owner_id": user["id"],
                        }
                    ),
                )
            self.sns.publish(
                TopicArn=self.topic_arn,
                Subject="CampusConnect listing published",
                Message=json.dumps(
                    {
                        "type": "listing.published",
                        "listing_id": listing["id"],
                        "title": listing["title"],
                        "owner_id": user["id"],
                    }
                ),
            )
        except (ClientError, BotoCoreError) as exc:
            raise provider_error("Amazon SQS/SNS", exc) from exc
        return self.repo.add_notification(
            user_id=user["id"],
            message=f"Your listing “{listing['title']}” was published. Amazon SNS accepted the notification.",
            channel="amazon-sns",
        )


def build_notifier(settings, repo):
    if settings.notification_backend == "local":
        return LocalNotifier(repo)
    if settings.notification_backend == "aws":
        session = aws_session(settings)
        config = aws_config()
        return AwsNotifier(
            repo,
            sqs=session.client("sqs", config=config),
            sns=session.client("sns", config=config),
            queue_url=settings.sqs_queue_url,
            topic_arn=settings.sns_topic_arn,
        )
    raise ConfigurationError(f"Unknown notification backend: {settings.notification_backend}")
