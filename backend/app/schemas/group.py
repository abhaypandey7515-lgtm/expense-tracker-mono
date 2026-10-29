from datetime import datetime
from typing import List

from pydantic import BaseModel, Field, field_validator


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name", mode="before")
    @classmethod
    def _strip(cls, v):
        return v.strip() if isinstance(v, str) else v


class GroupJoin(BaseModel):
    invite_code: str = Field(min_length=1, max_length=12)


class GroupOut(BaseModel):
    id: str
    name: str
    invite_code: str
    created_at: datetime


class MemberOut(BaseModel):
    user_id: str
    username: str
    display_name: str
    role: str


class GroupDetail(GroupOut):
    members: List[MemberOut]
