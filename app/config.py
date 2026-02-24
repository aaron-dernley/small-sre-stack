from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    aws_region: str = "us-east-1"
    dynamodb_table_name: str = "prima-tech-challenge-users"
    s3_bucket_name: str = "prima-tech-challenge"

    # Optional endpoint override for LocalStack or other compatible services
    aws_endpoint_url: Optional[str] = None

    # Override the public-facing S3 URL base when using LocalStack.
    # E.g. "http://localhost:4566/prima-tech-challenge"
    s3_public_url_base: Optional[str] = None

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
