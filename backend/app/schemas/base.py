from collections.abc import Callable
from datetime import datetime
from typing import Any

import pydantic_core.core_schema as core_schema
from bson import ObjectId
from pydantic import BaseModel, ConfigDict
from pydantic_core import CoreSchema


class ObjectIdStr(str):
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: Callable[[Any], CoreSchema]
    ) -> CoreSchema:
        return core_schema.with_info_plain_validator_function(
            function=cls._validate,
            json_schema_input_schema=core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )

    @classmethod
    def _validate(cls, v: Any, _info: Any) -> str:
        if isinstance(v, ObjectId):
            return str(v)
        if isinstance(v, str) and ObjectId.is_valid(v):
            return v
        raise ValueError("Invalid ObjectId")

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema_obj: CoreSchema, handler: Callable[[CoreSchema], CoreSchema]
    ) -> CoreSchema:
        return handler(core_schema.str_schema())


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
