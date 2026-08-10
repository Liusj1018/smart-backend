"""Domain models for Member."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field


class Role(StrEnum):
    """Member role within a team."""

    member = "member"
    admin = "admin"
    developer = "developer"
    viewer = "viewer"


class Member(BaseModel):
    """Domain model representing a team member."""

    id: Annotated[str, Field(description="Unique member identifier")]
    team_id: Annotated[str, Field(description="Owning team identifier")]
    name: Annotated[str, Field(min_length=1, max_length=100, description="Display name")]
    email: Annotated[EmailStr, Field(description="Email address")]
    role: Annotated[Role, Field(description="Team role")]
    github_username: Annotated[str | None, Field(default=None, max_length=100, description="GitHub handle")]
    created_at: Annotated[datetime, Field(description="Creation timestamp")]
    updated_at: Annotated[datetime, Field(description="Last update timestamp")]
