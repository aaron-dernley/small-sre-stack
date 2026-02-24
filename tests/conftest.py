"""Pytest fixtures shared across the test suite.

We use moto to intercept all AWS calls so tests run offline without any
real AWS credentials.  Environment variables are set *before* the app
modules are imported (via autouse fixtures) so pydantic-settings picks up
the test values and caches the correct Settings instance.
"""

import io
import os

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

# ---------------------------------------------------------------------------
# AWS credential stubs – required by moto before any boto3 call is made
# ---------------------------------------------------------------------------
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
os.environ.setdefault("AWS_SESSION_TOKEN", "testing")


TEST_TABLE = "test-users"
TEST_BUCKET = "test-prima-avatars"
TEST_REGION = "us-east-1"


@pytest.fixture(autouse=True)
def _set_test_env(monkeypatch):
    """Override config env vars for every test so the app targets test resources."""
    monkeypatch.setenv("DYNAMODB_TABLE_NAME", TEST_TABLE)
    monkeypatch.setenv("S3_BUCKET_NAME", TEST_BUCKET)
    monkeypatch.setenv("AWS_REGION", TEST_REGION)
    # Clear the lru_cache so Settings re-reads the patched env vars
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def aws_resources():
    """Spin up mocked DynamoDB + S3 resources for one test."""
    with mock_aws():
        dynamodb = boto3.client("dynamodb", region_name=TEST_REGION)
        dynamodb.create_table(
            TableName=TEST_TABLE,
            KeySchema=[{"AttributeName": "email", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "email", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        s3 = boto3.client("s3", region_name=TEST_REGION)
        s3.create_bucket(Bucket=TEST_BUCKET)

        yield {"dynamodb": dynamodb, "s3": s3}


@pytest.fixture
def client(aws_resources):
    """FastAPI test client wired to mocked AWS resources."""
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_image() -> bytes:
    """A minimal valid 1x1 PNG so we don't ship a binary fixture file."""
    # 1×1 transparent PNG (67 bytes) – public domain minimal PNG
    return bytes(
        [
            0x89,
            0x50,
            0x4E,
            0x47,
            0x0D,
            0x0A,
            0x1A,
            0x0A,
            0x00,
            0x00,
            0x00,
            0x0D,
            0x49,
            0x48,
            0x44,
            0x52,
            0x00,
            0x00,
            0x00,
            0x01,
            0x00,
            0x00,
            0x00,
            0x01,
            0x08,
            0x06,
            0x00,
            0x00,
            0x00,
            0x1F,
            0x15,
            0xC4,
            0x89,
            0x00,
            0x00,
            0x00,
            0x0A,
            0x49,
            0x44,
            0x41,
            0x54,
            0x78,
            0x9C,
            0x62,
            0x00,
            0x01,
            0x00,
            0x00,
            0x05,
            0x00,
            0x01,
            0x0D,
            0x0A,
            0x2D,
            0xB4,
            0x00,
            0x00,
            0x00,
            0x00,
            0x49,
            0x45,
            0x4E,
            0x44,
            0xAE,
            0x42,
            0x60,
            0x82,
        ]
    )


@pytest.fixture
def sample_image_file(sample_image) -> io.BytesIO:
    buf = io.BytesIO(sample_image)
    buf.name = "avatar.png"
    return buf
