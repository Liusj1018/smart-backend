"""Common schemas: pagination and RFC 7807 error format."""

from typing import Annotated

from pydantic import BaseModel, Field


class PaginationParams(BaseModel):
    """Pagination request parameters."""

    page: Annotated[int, Field(ge=1, description="Page number, starting from 1")] = 1
    page_size: Annotated[int, Field(ge=1, le=100, description="Items per page (1-100)")] = 20


class PageResponse[T](BaseModel):
    """Paginated response wrapper."""

    items: list[T]
    total: Annotated[int, Field(ge=0)]
    page: Annotated[int, Field(ge=1)]
    page_size: Annotated[int, Field(ge=1, le=100)]
    total_pages: Annotated[int, Field(ge=0)]

    @classmethod
    def make(
        cls,
        items: list[T],
        total: int,
        pagination: PaginationParams,
    ) -> "PageResponse[T]":
        """Build a paginated response from items, total count, and params."""
        total_pages = (total + pagination.page_size - 1) // pagination.page_size
        return cls(
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=total_pages,
        )


class ErrorResponse(BaseModel):
    """RFC 7807 Problem Details error response."""

    type: Annotated[str, Field(description="Error type URI or identifier")]
    title: Annotated[str, Field(description="Short human-readable summary")]
    status: Annotated[int, Field(description="HTTP status code")]
    detail: Annotated[str, Field(description="Human-readable explanation")]
    instance: Annotated[str, Field(description="Request path that caused the error")]
    trace_id: Annotated[str, Field(description="Unique trace ID for debugging")]


class DeleteResponse(BaseModel):
    """Generic delete success response."""

    message: Annotated[str, Field(description="Success message")] = "删除成功"
