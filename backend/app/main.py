from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .models import (
    Alert,
    Device,
    DeviceCreate,
    DeviceStateUpdate,
    ExecuteCommandRequest,
    ExecuteCommandResult,
    ParseCommandRequest,
    ParseCommandResponse,
    SensorReading,
    SensorReadingIn,
)
from .services import (
    create_device,
    execute_command,
    list_alerts,
    list_devices,
    list_readings,
    parse_command,
    reset_demo_data,
    save_reading,
    seed_demo_data,
    update_device_state,
)

app = FastAPI(title="Smart Home Backend", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/devices", response_model=Device)
def create_device_api(payload: DeviceCreate) -> Device:
    return create_device(payload)


@app.get("/api/devices", response_model=list[Device])
def list_devices_api() -> list[Device]:
    return list_devices()


@app.patch("/api/devices/{device_id}/state", response_model=Device)
def update_device_state_api(device_id: str, payload: DeviceStateUpdate) -> Device:
    try:
        return update_device_state(device_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/readings", response_model=SensorReading)
def create_reading_api(payload: SensorReadingIn) -> SensorReading:
    try:
        reading, _ = save_reading(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return reading


@app.get("/api/readings", response_model=list[SensorReading])
def list_readings_api(
    device_id: str | None = None, limit: int = Query(default=100, ge=1, le=1000)
) -> list[SensorReading]:
    return list_readings(device_id=device_id, limit=limit)


@app.get("/api/alerts", response_model=list[Alert])
def list_alerts_api(limit: int = Query(default=100, ge=1, le=500)) -> list[Alert]:
    return list_alerts(limit=limit)


@app.post("/api/llm/parse-command", response_model=ParseCommandResponse)
def parse_command_api(payload: ParseCommandRequest) -> ParseCommandResponse:
    return parse_command(payload.text)


@app.post("/api/control/execute", response_model=ExecuteCommandResult)
def execute_command_api(payload: ExecuteCommandRequest) -> ExecuteCommandResult:
    return execute_command(payload.text)


@app.post("/api/demo/seed")
def seed_demo_api() -> dict[str, Any]:
    return seed_demo_data()


@app.post("/api/demo/reset")
def reset_demo_api() -> dict[str, str]:
    return reset_demo_data()
