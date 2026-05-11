from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DeviceType(str, Enum):
    LIGHT = "light"
    SOCKET = "socket"
    SENSOR = "sensor"
    OTHER = "other"


class DeviceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    type: DeviceType = DeviceType.OTHER
    location: str = Field(default="unknown", max_length=64)


class Device(DeviceCreate):
    id: str
    status: str = "offline"
    state: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class DeviceStateUpdate(BaseModel):
    status: str | None = None
    state: dict[str, Any] | None = None


class SensorReadingIn(BaseModel):
    device_id: str = Field(min_length=1)
    temperature: float | None = None
    humidity: float | None = None
    gas_ppm: float | None = Field(default=None, ge=0)


class SensorReading(SensorReadingIn):
    id: str
    created_at: datetime = Field(default_factory=utc_now)


class Alert(BaseModel):
    id: str
    device_id: str
    level: str
    message: str
    reading_id: str
    created_at: datetime = Field(default_factory=utc_now)


class ParseCommandRequest(BaseModel):
    text: str = Field(min_length=1, max_length=200)


class ParsedCommand(BaseModel):
    action: str
    target: str
    value: str | float | int | None = None
    condition: str | None = None


class ParseCommandResponse(BaseModel):
    normalized_text: str
    commands: list[ParsedCommand]


class ExecuteCommandRequest(BaseModel):
    text: str = Field(min_length=1, max_length=200)


class ExecuteCommandResult(BaseModel):
    parsed: ParseCommandResponse
    updated_devices: list[Device]

