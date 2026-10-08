from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    field: str
    message: str
    code: str


class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    error_code: str
    errors: list[ErrorDetail] = Field(default_factory=list)


class SuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: Any = None


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_prev: bool


class PaginatedResponse(BaseModel):
    success: bool = True
    message: str
    data: Any = None
    pagination: PaginationMeta | None = None
