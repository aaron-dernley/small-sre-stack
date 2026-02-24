from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import EmailStr

from app.models.user import UserResponse
from app.services.dynamodb_service import DynamoDBService
from app.services.s3_service import S3Service

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_AVATAR_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


def get_dynamodb() -> DynamoDBService:
    return DynamoDBService()


def get_s3() -> S3Service:
    return S3Service()


@router.get(
    "/users",
    response_model=list[UserResponse],
    summary="List all users",
)
async def list_users(
    db: DynamoDBService = Depends(get_dynamodb),
) -> list[dict]:
    """Return every user stored in DynamoDB."""
    try:
        return db.list_users()
    except Exception as exc:
        logger.error("Failed to list users: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve users.",
        ) from exc


@router.post(
    "/user",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user",
)
async def create_user(
    name: str = Form(..., description="Full name of the user", min_length=1),
    email: EmailStr = Form(..., description="Unique email address"),
    avatar: UploadFile = File(..., description="Avatar image (JPEG, PNG, GIF, WebP)"),
    db: DynamoDBService = Depends(get_dynamodb),
    s3: S3Service = Depends(get_s3),
) -> UserResponse:
    """Create a user, upload their avatar to S3, and persist metadata in DynamoDB."""
    # Validate content type
    if avatar.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported file type '{avatar.content_type}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}"
            ),
        )

    file_content = await avatar.read()

    if len(file_content) > MAX_AVATAR_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Avatar file exceeds the 5 MB limit.",
        )

    ext = avatar.filename.rsplit(".", 1)[-1].lower() if "." in (avatar.filename or "") else "png"
    file_key = f"avatars/{uuid.uuid4()}.{ext}"

    try:
        avatar_url = s3.upload_avatar(file_content, file_key, avatar.content_type)
    except Exception as exc:
        logger.error("Avatar upload failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar.",
        ) from exc

    try:
        db.put_user(name=name, email=email, avatar_url=avatar_url)
    except Exception as exc:
        logger.error("User persistence failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save user.",
        ) from exc

    return UserResponse(name=name, email=email, avatar_url=avatar_url)
