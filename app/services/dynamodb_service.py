from __future__ import annotations

import logging

import boto3
from botocore.exceptions import ClientError

from app.config import get_settings

logger = logging.getLogger(__name__)


class DynamoDBService:
    """Thin wrapper around the DynamoDB client for user persistence."""

    def __init__(self) -> None:
        settings = get_settings()
        kwargs: dict = {"region_name": settings.aws_region}
        if settings.aws_endpoint_url:
            kwargs["endpoint_url"] = settings.aws_endpoint_url
        self._client = boto3.client("dynamodb", **kwargs)
        self._table_name = settings.dynamodb_table_name

    def put_user(self, name: str, email: str, avatar_url: str) -> None:
        """Write (or overwrite) a user item in DynamoDB."""
        try:
            self._client.put_item(
                TableName=self._table_name,
                Item={
                    "email": {"S": email},
                    "name": {"S": name},
                    "avatar_url": {"S": avatar_url},
                },
            )
        except ClientError as exc:
            logger.error("DynamoDB put_item failed: %s", exc)
            raise

    def list_users(self) -> list[dict]:
        """Return all users as plain dicts."""
        try:
            response = self._client.scan(TableName=self._table_name)
        except ClientError as exc:
            logger.error("DynamoDB scan failed: %s", exc)
            raise

        return [
            {
                "name": item["name"]["S"],
                "email": item["email"]["S"],
                "avatar_url": item["avatar_url"]["S"],
            }
            for item in response.get("Items", [])
        ]
