import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.]+$")


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    display_name: Optional[str] = Field(default=None, max_length=100)

    @field_validator("username")
    @classmethod
    def _username_chars(cls, v: str) -> str:
        v = v.strip()
        if not _USERNAME_RE.match(v):
            raise ValueError("Username may contain only letters, digits, '_' and '.'")
        return v


class LoginRequest(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=128)


class UserOut(BaseModel):
    id: str
    username: str
    display_name: str


class TokenResponse(BaseModel):
    token: str
    expires_at: datetime
    user: UserOut
