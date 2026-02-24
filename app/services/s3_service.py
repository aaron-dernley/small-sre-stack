from __future__ import annotations

import logging

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config import get_settings

logger = logging.getLogger(__name__)


class S3Service:
    """Handles avatar uploads to S3 (or any S3-compatible store)."""

    def __init__(self) -> None:
        settings = get_settings()
        kwargs: dict = {"region_name": settings.aws_region}
        if settings.aws_endpoint_url:
            kwargs["endpoint_url"] = settings.aws_endpoint_url
            # Force path-style addressing so requests go to
            # http://localstack:4566/<bucket>/... instead of
            # http://<bucket>.localstack:4566/... (the subdomain won't resolve).
            kwargs["config"] = Config(s3={"addressing_style": "path"})
        self._client = boto3.client("s3", **kwargs)
        self._bucket_name = settings.s3_bucket_name
        self._settings = settings

    def upload_avatar(
        self, file_content: bytes, file_key: str, content_type: str
    ) -> str:
        """Upload avatar bytes and return its public URL.

        When ``S3_PUBLIC_URL_BASE`` is set (e.g. for LocalStack), that base is
        used so the URL is reachable from outside the Docker network.
        """
        try:
            self._client.put_object(
                Bucket=self._bucket_name,
                Key=file_key,
                Body=file_content,
                ContentType=content_type,
            )
        except ClientError as exc:
            logger.error("S3 put_object failed: %s", exc)
            raise

        if self._settings.s3_public_url_base:
            base = self._settings.s3_public_url_base.rstrip("/")
            return f"{base}/{file_key}"

        return (
            f"https://{self._bucket_name}.s3.{self._settings.aws_region}"
            f".amazonaws.com/{file_key}"
        )
