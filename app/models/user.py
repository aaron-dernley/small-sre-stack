from __future__ import annotations

from pydantic import BaseModel


class UserResponse(BaseModel):
    name: str
    email: str
    avatar_url: str
