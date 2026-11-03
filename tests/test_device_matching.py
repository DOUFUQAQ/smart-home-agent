"""设备匹配与命令执行的行为断言。

``services._find_devices_by_target`` / ``execute_command`` 的核心逻辑已抽到
``app.parser.devices_for_target`` / ``apply_command`` / ``execute_commands``，
这里用普通 Python 对象当"设备"，因此不需要 pydantic 或 fastapi。
"""

from __future__ import annotations

import unittest

import tests  # noqa: F401  # 触发 sys.path 设置
from app.parser import (
    TARGET_DEVICE_TYPES,
    apply_command,
    device_type_name,
    devices_for_target,
    execute_commands,
    parse_command_text,
)


class FakeDevice:
    """最小设备替身：只需要 type / status / state 三个属性。"""

    def __init__(
        self,
        name: str,
        device_type: str,
        location: str = "lab",
        status: str = "offline",
        state: dict | None = None,
    ) -> None:
        self.name = name
        self.type = device_type
        self.location = location
        self.status = status
        self.state = dict(state or {})

    def __repr__(self) -> str:  # pragma: no cover - 便于断言失败时阅读
        return f"FakeDevice({self.name!r}, {self.type!r})"


class EnumLikeType:
    """模拟 ``DeviceType(str, Enum)``：真实模型里 type 是枚举而不是 str。"""

    def __init__(self, value: str) -> None:
        self.value = value

    def __str__(self) -> str:  # pragma: no cover
        return self.value


def demo_devices() -> list[FakeDevice]:
    return [
        FakeDevice("客厅主灯", "light", "客厅"),
        FakeDevice("卧室灯", "light", "卧室"),
        FakeDevice("卧室插座", "socket", "卧室"),
        FakeDevice("智能风扇", "other", "阳台"),
        FakeDevice("环境传感器", "sensor", "客厅"),
    ]


class DeviceTypeNameTest(unittest.TestCase):
    def test_plain_string_type(self) -> None:
        self.assertEqual(device_type_name(FakeDevice("灯", "light")), "light")

    def test_enum_like_type_uses_value(self) -> None:
        device = FakeDevice("灯", "light")
        device.type = EnumLikeType("light")
        self.assertEqual(device_type_name(device), "light")

    def test_missing_type_is_empty_string(self) -> None:
        self.assertEqual(device_type_name(object()), "")


class DevicesForTargetTest(unittest.TestCase):
    def test_light_matches_all_lights(self) -> None:
        # 只按 type 匹配，不看 location：客厅灯和卧室灯会同时被命中
        matched = devices_for_target(demo_devices(), "light")
        self.assertEqual([item.name for item in matched], ["客厅主灯", "卧室灯"])

    def test_socket_matches_only_socket(self) -> None:
        matched = devices_for_target(demo_devices(), "socket")
        self.assertEqual([item.name for item in matched], ["卧室插座"])

    def test_fan_and_ac_both_map_to_other(self) -> None:
        # 已知缺陷：没有 fan / ac 设备类型，两者都落到 other
        fan = devices_for_target(demo_devices(), "fan")
        ac = devices_for_target(demo_devices(), "ac")
        self.assertEqual([item.name for item in fan], ["智能风扇"])
        self.assertEqual([item.name for item in ac], ["智能风扇"])
        self.assertEqual(TARGET_DEVICE_TYPES["fan"], TARGET_DEVICE_TYPES["ac"])

    def test_sensor_is_not_addressable(self) -> None:
        # 没有任何指令目标映射到 sensor，因此传感器永远不会被语音控制到
        for target in TARGET_DEVICE_TYPES:
            matched = [item.name for item in devices_for_target(demo_devices(), target)]
            self.assertNotIn("环境传感器", matched)

    def test_unknown_target_matches_nothing(self) -> None:
        self.assertEqual(devices_for_target(demo_devices(), "unknown"), [])
        self.assertEqual(devices_for_target(demo_devices(), "sensor"), [])

    def test_empty_device_list(self) -> None:
        self.assertEqual(devices_for_target([], "light"), [])


class ApplyCommandTest(unittest.TestCase):
    def test_turn_on(self) -> None:
        device = FakeDevice("客厅主灯", "light")
        changed = apply_command(device, {"action": "turn_on", "target": "light"})
        self.assertTrue(changed)
        self.assertEqual(device.status, "online")
        self.assertEqual(device.state["power"], "on")

    def test_turn_off(self) -> None:
        device = FakeDevice("卧室插座", "socket", state={"power": "on"})
        changed = apply_command(device, {"action": "turn_off", "target": "socket"})
        self.assertTrue(changed)
        self.assertEqual(device.state["power"], "off")

    def test_set_brightness_writes_literal_up(self) -> None:
        device = FakeDevice("客厅主灯", "light")
        changed = apply_command(device, {"action": "set_brightness", "target": "light"})
        self.assertTrue(changed)
        self.assertEqual(device.state["brightness"], "up")

    def test_conditional_turn_on_records_condition(self) -> None:
        device = FakeDevice("智能风扇", "other")
        command = {
            "action": "conditional_turn_on",
            "target": "fan",
            "condition": "temperature>30.0",
        }
        changed = apply_command(device, command)
        self.assertTrue(changed)
        self.assertEqual(device.state["power"], "on")
        self.assertEqual(device.state["condition"], "temperature>30.0")

    def test_unknown_action_does_not_touch_device(self) -> None:
        device = FakeDevice("客厅主灯", "light")
        changed = apply_command(device, {"action": "unknown", "target": "unknown"})
        self.assertFalse(changed)
        self.assertEqual(device.state, {})
        self.assertEqual(device.status, "offline")

    def test_turn_on_marks_offline_device_online(self) -> None:
        # 语义上有点混：一条控制命令会顺手把 status 改成 online
        device = FakeDevice("客厅主灯", "light", status="offline")
        apply_command(device, {"action": "turn_on", "target": "light"})
        self.assertEqual(device.status, "online")


class ExecuteCommandsTest(unittest.TestCase):
    def test_execute_open_main_light(self) -> None:
        devices = demo_devices()
        commands = parse_command_text("打开客厅主灯")["commands"]
        updated = execute_commands(commands, devices)
        # 所有 light 类型都会被打中，包括没被点名的卧室灯
        self.assertEqual(len(updated), 2)
        self.assertTrue(all(item.state["power"] == "on" for item in updated))

    def test_execute_close_socket(self) -> None:
        devices = demo_devices()
        commands = parse_command_text("关闭卧室插座")["commands"]
        updated = execute_commands(commands, devices)
        self.assertEqual(len(updated), 1)
        self.assertEqual(updated[0].name, "卧室插座")
        self.assertEqual(updated[0].state["power"], "off")

    def test_execute_open_fan_only_touches_other_devices(self) -> None:
        devices = demo_devices()
        commands = parse_command_text("打开风扇")["commands"]
        updated = execute_commands(commands, devices)
        self.assertEqual([item.name for item in updated], ["智能风扇"])
        light = next(item for item in devices if item.type == "light")
        self.assertEqual(light.state, {})

    def test_execute_unknown_changes_nothing(self) -> None:
        devices = demo_devices()
        commands = parse_command_text("客厅温度多少")["commands"]
        self.assertEqual(execute_commands(commands, devices), [])
        self.assertTrue(all(item.status == "offline" for item in devices))
        self.assertTrue(all(item.state == {} for item in devices))

    def test_same_device_can_be_updated_twice_in_one_sentence(self) -> None:
        # "打开风扇和空调"：fan 与 ac 都映射到 other，同一台设备被改两次
        devices = demo_devices()
        commands = parse_command_text("打开风扇和空调")["commands"]
        self.assertEqual(len(commands), 2)
        updated = execute_commands(commands, devices)
        self.assertEqual(len(updated), 2)
        self.assertIs(updated[0], updated[1])

    def test_contradictory_sentence_ends_up_off(self) -> None:
        devices = demo_devices()
        commands = parse_command_text("打开灯然后关闭灯")["commands"]
        updated = execute_commands(commands, devices)
        self.assertEqual(len(updated), 4)  # 2 条命令 × 2 台灯
        for device in (item for item in devices if item.type == "light"):
            self.assertEqual(device.state["power"], "off")

    def test_conditional_command_sets_condition_flag(self) -> None:
        devices = demo_devices()
        commands = parse_command_text("如果温度超过30度就打开风扇")["commands"]
        updated = execute_commands(commands, devices)
        self.assertTrue(updated)
        for device in updated:
            self.assertEqual(device.state["condition"], "temperature>30.0")


if __name__ == "__main__":
    unittest.main()
