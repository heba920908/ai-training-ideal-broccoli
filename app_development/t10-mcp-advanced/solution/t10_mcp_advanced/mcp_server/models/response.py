from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorResponse(BaseModel):
    code: int
    message: str
    data: dict[str, Any] | None = None


class MCPResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: str | int | None = None
    result: dict[str, Any] | None = Field(default=None)
    error: ErrorResponse | None = Field(default=None)

    model_config = ConfigDict(extra="allow")
