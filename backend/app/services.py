"""业务层：pydantic 模型 ↔ 纯规则引擎（app/parser.py）↔ 进程内存储（app/store.py）。

这一层刻意保持很薄，只做三件事：

1. 把 dict 形式的解析结果 / 告警描述转成 pydantic 模型；
2. 读写 ``store`` 里的内存集合；
3. 生成 uuid 与时间戳。

真正的规则（关键词、正则、阈值、设备匹配）都在 :mod:`app.parser` 里，
不依赖任何第三方包，因此可以脱离 fastapi / pydantic 单独测试。

⚠ 关于"大模型"：本文件里**没有任何**模型调用，``parse_command`` 走的是
关键词 + 正则。HTTP 路由叫 ``/api/llm/parse-command`` 是沿用了原始命名，
真实实现见 :func:`app.parser.parse_command_text`。
"""

from __future__ import annotations

from typing import Any, Iterable
from uuid import uuid4

from .models import (
    Alert,
    Device,
    DeviceCreate,
    DeviceStateUpdate,
    ExecuteCommandResult,
    ParseCommandResponse,
    ParsedCommand,
    SensorReading,
    SensorReadingIn,
)
from .parser import (  # noqa: F401  # 阈值与 normalize_text 仍可从 services 导入
    GAS_THRESHOLD,
    TEMP_THRESHOLD,
    detect_alerts,
    devices_for_target,
    execute_commands,
    normalize_text,
    parse_command_text,
)
from .store import store


def create_device(payload: DeviceCreate) -> Device:
    device = Device(id=str(uuid4()), **payload.model_dump())
    store.devices[device.id] = device
    return device


def update_device_state(device_id: str, payload: DeviceStateUpdate) -> Device:
    device = get_device(device_id)
    data = payload.model_dump(exclude_none=True)
    if "status" in data:
        device.status = data["status"]
    if "state" in data:
        device.state.update(data["state"])
    return device


def get_device(device_id: str) -> Device:
    device = store.devices.get(device_id)
    if not device:
        raise KeyError(f"device {device_id} not found")
    return device


def list_devices() -> list[Device]:
    return list(store.devices.values())


def save_reading(payload: SensorReadingIn) -> tuple[SensorReading, list[Alert]]:
    _ = get_device(payload.device_id)
    reading = SensorReading(id=str(uuid4()), **payload.model_dump())
    store.readings.appendleft(reading)
    alerts = evaluate_alerts(reading)
    for alert in alerts:
        store.alerts.appendleft(alert)
    return reading, alerts


def list_readings(device_id: str | None = None, limit: int = 100) -> list[SensorReading]:
    items = list(store.readings)
    if device_id:
        items = [x for x in items if x.device_id == device_id]
    return items[:limit]


def list_alerts(limit: int = 100) -> list[Alert]:
    return list(store.alerts)[:limit]


def reset_demo_data() -> dict[str, str]:
    store.clear()
    return {"status": "ok", "message": "demo data cleared"}


def seed_demo_data() -> dict[str, Any]:
    store.clear()

    devices = [
        create_device(DeviceCreate(name="客厅主灯", type="light", location="客厅")),
        create_device(DeviceCreate(name="卧室插座", type="socket", location="卧室")),
        create_device(DeviceCreate(name="环境传感器", type="sensor", location="客厅")),
        create_device(DeviceCreate(name="智能风扇", type="other", location="阳台")),
    ]

    light, socket, sensor, fan = devices

    update_device_state(
        light.id,
        DeviceStateUpdate(status="online", state={"power": "on", "brightness": "70%"}),
    )
    update_device_state(
        socket.id,
        DeviceStateUpdate(status="online", state={"power": "off"}),
    )
    update_device_state(
        fan.id,
        DeviceStateUpdate(status="online", state={"power": "off", "mode": "auto"}),
    )

    demo_readings = [
        SensorReadingIn(device_id=sensor.id, temperature=24.6, humidity=42.0, gas_ppm=78.0),
        SensorReadingIn(device_id=sensor.id, temperature=26.3, humidity=43.8, gas_ppm=96.0),
        SensorReadingIn(device_id=sensor.id, temperature=28.7, humidity=47.1, gas_ppm=135.0),
        SensorReadingIn(device_id=sensor.id, temperature=31.2, humidity=52.4, gas_ppm=180.0),
        SensorReadingIn(device_id=sensor.id, temperature=32.4, humidity=55.3, gas_ppm=338.0),
        SensorReadingIn(device_id=sensor.id, temperature=29.5, humidity=48.9, gas_ppm=120.0),
    ]

    total_alerts = 0
    for reading in demo_readings:
        _, alerts = save_reading(reading)
        total_alerts += len(alerts)

    demo_commands = [
        "打开客厅主灯",
        "关闭卧室插座",
        "打开风扇",
        "如果温度超过30度就打开风扇",
        "把客厅主灯调亮一点",
    ]

    return {
        "status": "ok",
        "message": "demo data seeded",
        "counts": {
            "devices": len(store.devices),
            "readings": len(store.readings),
            "alerts": total_alerts,
            "commands": len(demo_commands),
        },
        "demo_commands": demo_commands,
    }


def evaluate_alerts(reading: SensorReading) -> list[Alert]:
    """按阈值判定告警，规则本身在 :func:`app.parser.detect_alerts`。"""
    return [
        Alert(
            id=str(uuid4()),
            device_id=reading.device_id,
            level=item["level"],
            message=item["message"],
            reading_id=reading.id,
        )
        for item in detect_alerts(reading.temperature, reading.gas_ppm)
    ]


def parse_command(text: str) -> ParseCommandResponse:
    """解析一句指令（关键词 + 正则，不调用大模型）。"""
    parsed = parse_command_text(text)
    return ParseCommandResponse(
        normalized_text=parsed["normalized_text"],
        commands=[ParsedCommand(**item) for item in parsed["commands"]],
    )


def execute_command(text: str) -> ExecuteCommandResult:
    """解析并就地修改设备状态；``unknown`` 命令不会命中任何设备。"""
    parsed = parse_command(text)
    commands = [item.model_dump() for item in parsed.commands]
    updated = execute_commands(commands, store.devices.values())
    return ExecuteCommandResult(parsed=parsed, updated_devices=updated)


def _find_devices_by_target(target: str) -> Iterable[Device]:
    """按目标筛选设备，映射表见 :data:`app.parser.TARGET_DEVICE_TYPES`。"""
    return devices_for_target(store.devices.values(), target)
