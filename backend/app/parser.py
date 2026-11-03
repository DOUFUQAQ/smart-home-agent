"""纯规则引擎：自然语言指令解析、设备匹配、告警判定。

这个模块**只依赖标准库**，不 import pydantic / fastapi，因此可以在
没有任何第三方包的环境里直接单测（见仓库根目录 ``tests/``）。

设计上的取舍：原工程的 ``services.py`` 把「规则逻辑」和「pydantic 模型
转换 + 进程内存储」写在同一个文件里，导致想测一条指令怎么被解析都必须先
装上 fastapi 全家桶。这里把纯函数抽出来，``services.py`` 只剩下
「dict ↔ pydantic 模型」的薄封装，行为完全不变。

注意：本模块**没有调用任何大模型**。指令解析是关键词 + 一条正则，
见 :func:`parse_command_text`。
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

# ---- 告警阈值（原 services.py 中的模块级常量） ----
TEMP_THRESHOLD = 30.0
GAS_THRESHOLD = 300.0

# ---- 指令目标词表 ----
# 顺序即解析输出顺序，改顺序会改变 ParseCommandResponse.commands 的顺序。
TARGET_KEYWORDS: dict[str, tuple[str, ...]] = {
    "light": ("灯", "照明", "主灯"),
    "socket": ("插座",),
    "fan": ("风扇", "风机"),
    "ac": ("空调",),
}

# ---- 指令目标 → 设备类型 ----
# 已知缺陷：没有 fan / ac 类型，两者都被硬映射到 other，
# 所以「打开风扇」会命中所有 type=other 的设备（详见 README「已知局限」）。
TARGET_DEVICE_TYPES: dict[str, frozenset[str]] = {
    "light": frozenset({"light"}),
    "socket": frozenset({"socket"}),
    "fan": frozenset({"other"}),
    "ac": frozenset({"other"}),
}

TURN_ON_WORDS: tuple[str, ...] = ("打开", "开启")
TURN_OFF_WORDS: tuple[str, ...] = ("关闭",)
BRIGHTEN_WORDS: tuple[str, ...] = ("调亮", "亮一点")

TEMP_CONDITION_PATTERN = re.compile(r"温度(超过|高于|大于)(\d+(?:\.\d+)?)")

ACTION_TURN_ON = "turn_on"
ACTION_TURN_OFF = "turn_off"
ACTION_SET_BRIGHTNESS = "set_brightness"
ACTION_CONDITIONAL_TURN_ON = "conditional_turn_on"
ACTION_UNKNOWN = "unknown"


def normalize_text(text: str) -> str:
    """去首尾空白、压掉重复空白、转小写。"""
    return " ".join(text.strip().lower().split())


def _contains_any(text: str, words: Iterable[str]) -> bool:
    return any(word in text for word in words)


def _command(
    action: str,
    target: str,
    value: str | float | int | None = None,
    condition: str | None = None,
) -> dict[str, Any]:
    return {"action": action, "target": target, "value": value, "condition": condition}


def parse_command_text(text: str) -> dict[str, Any]:
    """把一句中文指令解析成结构化命令列表。

    解析流程（纯关键词 + 正则，**没有**模型参与）：

    1. :func:`normalize_text` 归一化；
    2. 按 :data:`TARGET_KEYWORDS` 顺序逐个目标命中；命中目标后，
       再分别检查句子里有没有「打开/开启」「关闭」「调亮/亮一点」，
       每种动词各产出一条命令（同一句可产出多条）；
    3. 再用正则 ``温度(超过|高于|大于)<数字>`` 匹配条件指令，
       句中提到「空调」就作用于 ``ac``，否则作用于 ``fan``；
    4. 一条都没命中则产出 ``unknown``。

    返回 ``{"normalized_text": str, "commands": [ {action, target, value, condition} ]}``，
    结构与 ``app.models.ParseCommandResponse`` 一一对应。
    """
    normalized = normalize_text(text)
    commands: list[dict[str, Any]] = []

    for target, keywords in TARGET_KEYWORDS.items():
        if not _contains_any(normalized, keywords):
            continue
        if _contains_any(normalized, TURN_ON_WORDS):
            commands.append(_command(ACTION_TURN_ON, target))
        if _contains_any(normalized, TURN_OFF_WORDS):
            commands.append(_command(ACTION_TURN_OFF, target))
        if _contains_any(normalized, BRIGHTEN_WORDS):
            commands.append(_command(ACTION_SET_BRIGHTNESS, target, value="up"))

    temp_match = TEMP_CONDITION_PATTERN.search(normalized)
    if temp_match and _contains_any(normalized, TURN_ON_WORDS):
        value = float(temp_match.group(2))
        target = "ac" if "空调" in normalized else "fan"
        commands.append(
            _command(ACTION_CONDITIONAL_TURN_ON, target, condition=f"temperature>{value}")
        )

    if not commands:
        commands.append(_command(ACTION_UNKNOWN, "unknown"))

    return {"normalized_text": normalized, "commands": commands}


def device_type_name(device: Any) -> str:
    """取设备的类型名，``DeviceType`` 枚举和普通字符串都能处理。"""
    value = getattr(device, "type", "")
    return getattr(value, "value", value)


def devices_for_target(devices: Iterable[Any], target: str) -> list[Any]:
    """按指令目标筛选设备。

    只按 ``type`` 匹配，**不看** ``location`` / ``name``，
    所以「打开客厅灯」和「打开卧室灯」会落到同一批设备上。
    """
    types = TARGET_DEVICE_TYPES.get(target, frozenset())
    if not types:
        return []
    return [device for device in devices if device_type_name(device) in types]


def apply_command(device: Any, command: Mapping[str, Any]) -> bool:
    """把一条命令作用到设备上，返回是否真的改动了设备。

    就地修改 ``device.status`` / ``device.state``（设备可以是 pydantic 模型，
    也可以是任何带这两个属性的对象，测试里用普通类即可）。
    """
    action = command.get("action")

    if action in (ACTION_TURN_ON, ACTION_CONDITIONAL_TURN_ON):
        device.status = "online"
        device.state["power"] = "on"
        condition = command.get("condition")
        if condition:
            device.state["condition"] = condition
        return True

    if action == ACTION_TURN_OFF:
        device.status = "online"
        device.state["power"] = "off"
        return True

    if action == ACTION_SET_BRIGHTNESS:
        device.status = "online"
        device.state["brightness"] = "up"
        return True

    return False


def execute_commands(commands: Iterable[Mapping[str, Any]], devices: Iterable[Any]) -> list[Any]:
    """按顺序执行命令，返回被改动过的设备列表（可能含重复项，与原实现一致）。"""
    device_list = list(devices)
    updated: list[Any] = []
    for command in commands:
        for device in devices_for_target(device_list, str(command.get("target"))):
            if apply_command(device, command):
                updated.append(device)
    return updated


def detect_alerts(
    temperature: float | None,
    gas_ppm: float | None,
    *,
    temp_threshold: float = TEMP_THRESHOLD,
    gas_threshold: float = GAS_THRESHOLD,
) -> list[dict[str, Any]]:
    """按阈值产生告警描述（严格大于；等于阈值不告警）。

    返回 ``[{"level": ..., "message": ...}]``，由 ``services.evaluate_alerts``
    补上 id / device_id / reading_id 后转成 ``Alert`` 模型。
    """
    alerts: list[dict[str, Any]] = []

    if temperature is not None and temperature > temp_threshold:
        alerts.append({"level": "warning", "message": f"温度过高: {temperature}°C"})

    if gas_ppm is not None and gas_ppm > gas_threshold:
        alerts.append({"level": "critical", "message": f"可燃气体浓度异常: {gas_ppm} ppm"})

    return alerts


