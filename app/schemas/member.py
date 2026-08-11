"""Request/response schemas for Member endpoints."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.member import Role
from app.schemas.common import PageResponse


class MemberCreate(BaseModel):
    """Request body for creating a member."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "张三",
                "email": "zhangsan@example.com",
                "password": "SecurePass123!",
                "role": "developer",
                "github_username": "zhangsan",
            }
        }
    )

    name: Annotated[str, Field(min_length=1, max_length=100, description="Display name")]
    email: Annotated[EmailStr, Field(description="Email address")]
    password: Annotated[str, Field(min_length=6, max_length=128, description="Login password (min 6 chars)")]
    role: Annotated[Role, Field(description="Team role")]
    github_username: Annotated[str | None, Field(default=None, max_length=100, description="GitHub handle")] = None


class MemberUpdate(BaseModel):
    """Request body for updating a member."""

    name: Annotated[str | None, Field(default=None, min_length=1, max_length=100)] = None
    email: Annotated[EmailStr | None, Field(default=None)] = None
    role: Annotated[Role | None, Field(default=None)] = None
    github_username: Annotated[str | None, Field(default=None, max_length=100)] = None


class MemberResponse(BaseModel):
    """Response schema for a single member."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    team_id: str
    name: str
    email: EmailStr
    role: Role
    github_username: str | None
    created_at: datetime
    updated_at: datetime


class PaginatedMembers(PageResponse[MemberResponse]):
    """Paginated list of members."""

    @classmethod
    def create(
        cls,
        items: list[MemberResponse],
        total: int,
        page: int,
        page_size: int,
    ) -> "PaginatedMembers":
        """Build a paginated response."""
        total_pages = (total + page_size - 1) // page_size
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )


class SuccessResponse(BaseModel):
    """Generic success response."""

    message: str
