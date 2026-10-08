from collections.abc import Callable
from datetime import datetime
from typing import Any

import pydantic_core.core_schema as core_schema
from bson import ObjectId
from pydantic import BaseModel, ConfigDict
from pydantic_core import CoreSchema


class ObjectIdStr(str):
    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema_obj: CoreSchema, handler: Callable[[CoreSchema], CoreSchema]
    ) -> CoreSchema:
        return handler(core_schema.str_schema())

    @classmethod
    def validate(cls, v: Any) -> str:
        if isinstance(v, ObjectId):
            return str(v)
        if isinstance(v, str) and ObjectId.is_valid(v):
            return v
        raise ValueError("Invalid ObjectId")


class BaseSchema(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )


class TimestampMixin(BaseModel):
    created_at: datetime
    updated_at: datetime


class SoftDeleteMixin(BaseModel):
    is_deleted: bool = False
    deleted_at: datetime | None = None
