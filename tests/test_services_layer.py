"""``app.services`` 这一层的回归测试（需要 pydantic）。

核心规则已在 ``tests/test_command_parser.py`` / ``tests/test_device_matching.py``
/ ``tests/test_alert_rules.py`` 里用纯逻辑覆盖；这个文件只验证"薄封装"没有
走样：pydantic 模型 ↔ dict 转换、进程内存储读写、以及 ``services`` 与
``parser`` 的输出是否一致。

没装 pydantic 的机器上整个文件会被跳过（不影响核心逻辑的测试覆盖）。
装了 pydantic 之后：

    pip install -r requirements.txt
    python -m unittest discover -s tests -t .
"""

from __future__ import annotations

import unittest

import tests  # noqa: F401  # 触发 sys.path 设置
from app.parser import detect_alerts, parse_command_text

try:  # pragma: no cover - 取决于环境
    from app import services
    from app.models import Alert, DeviceCreate, DeviceStateUpdate, SensorReadingIn
    from app.store import store

    HAS_PYDANTIC = True
    IMPORT_ERROR = ""
except Exception as exc:  # noqa: BLE001  # pragma: no cover
    HAS_PYDANTIC = False
    IMPORT_ERROR = f"{type(exc).__name__}: {exc}"


@unittest.skipUnless(
    HAS_PYDANTIC,
    f"需要 pydantic（pip install -r requirements.txt）：{IMPORT_ERROR}",
)
class ServicesContractTest(unittest.TestCase):
    """公共夹具：每个用例前后清空进程内存储。"""

    def setUp(self) -> None:
        store.clear()

    def tearDown(self) -> None:
        store.clear()

    def add_light(self, name: str = "客厅主灯", location: str = "客厅"):
        return services.create_device(DeviceCreate(name=name, type="light", location=location))

    def add_other(self, name: str = "智能风扇"):
        return services.create_device(DeviceCreate(name=name, type="other", location="阳台"))


class ParseCommandParityTest(ServicesContractTest):
    def test_services_matches_parser_for_every_sample(self) -> None:
        samples = [
            "打开客厅主灯",
            "关闭卧室插座",
            "把客厅主灯调亮一点",
            "如果温度超过30度就打开风扇",
            "请打开客厅主灯，再调亮一点",
            "把卧室空调调到 26 度",
            "客厅温度多少",
            "开灯",
            "",
        ]
        for text in samples:
            with self.subTest(text=text):
                from_parser = parse_command_text(text)
                from_services = services.parse_command(text)
                self.assertEqual(from_services.normalized_text, from_parser["normalized_text"])
                self.assertEqual(
                    [item.model_dump() for item in from_services.commands],
                    from_parser["commands"],
                )

    def test_parse_returns_pydantic_response(self) -> None:
        response = services.parse_command("打开客厅主灯")
        self.assertEqual(type(response).__name__, "ParseCommandResponse")
        self.assertEqual(response.commands[0].action, "turn_on")


class ExecuteCommandTest(ServicesContractTest):
    def test_execute_open_light(self) -> None:
        light = self.add_light()
        result = services.execute_command("打开客厅主灯")
        self.assertEqual(len(result.updated_devices), 1)
        self.assertEqual(result.updated_devices[0].id, light.id)
        self.assertEqual(light.state["power"], "on")
        self.assertEqual(light.status, "online")

    def test_execute_close_socket(self) -> None:
        socket = services.create_device(DeviceCreate(name="卧室插座", type="socket"))
        result = services.execute_command("关闭卧室插座")
        self.assertEqual(len(result.updated_devices), 1)
        self.assertEqual(socket.state["power"], "off")

    def test_execute_fan_hits_other_type(self) -> None:
        fan = self.add_other()
        result = services.execute_command("打开风扇")
        self.assertEqual([item.id for item in result.updated_devices], [fan.id])

    def test_execute_unknown_updates_nothing(self) -> None:
        self.add_light()
        result = services.execute_command("客厅温度多少")
        self.assertEqual(result.updated_devices, [])
        self.assertEqual(result.parsed.commands[0].action, "unknown")

    def test_execute_with_no_devices(self) -> None:
        result = services.execute_command("打开客厅主灯")
        self.assertEqual(result.updated_devices, [])


class FindDevicesByTargetTest(ServicesContractTest):
    def test_find_light_and_fan(self) -> None:
        light = self.add_light()
        fan = self.add_other()
        self.assertEqual(
            [item.id for item in services._find_devices_by_target("light")], [light.id]
        )
        self.assertEqual([item.id for item in services._find_devices_by_target("fan")], [fan.id])

    def test_find_unknown_target(self) -> None:
        self.add_light()
        self.assertEqual(list(services._find_devices_by_target("unknown")), [])


class EvaluateAlertsTest(ServicesContractTest):
    def test_evaluate_alerts_parity(self) -> None:
        device = services.create_device(DeviceCreate(name="环境传感器", type="sensor"))
        reading = SensorReadingIn(
            device_id=device.id, temperature=34.2, humidity=45.0, gas_ppm=450.0
        )
        saved, alerts = services.save_reading(reading)
        self.assertEqual(len(alerts), 2)
        self.assertTrue(all(isinstance(item, Alert) for item in alerts))
        self.assertEqual(
            [(item.level, item.message) for item in alerts],
            [(item["level"], item["message"]) for item in detect_alerts(34.2, 450.0)],
        )
        self.assertTrue(all(item.reading_id == saved.id for item in alerts))
        self.assertEqual(len(services.list_alerts()), 2)

    def test_no_alert_below_threshold(self) -> None:
        device = services.create_device(DeviceCreate(name="环境传感器", type="sensor"))
        _, alerts = services.save_reading(
            SensorReadingIn(device_id=device.id, temperature=24.6, gas_ppm=78.0)
        )
        self.assertEqual(alerts, [])

    def test_reading_for_unknown_device_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            services.save_reading(SensorReadingIn(device_id="missing", temperature=20.0))


class SeedDemoDataTest(ServicesContractTest):
    def test_seed_counts(self) -> None:
        payload = services.seed_demo_data()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["counts"]["devices"], 4)
        self.assertEqual(payload["counts"]["readings"], 6)
        self.assertEqual(payload["counts"]["alerts"], 3)
        self.assertEqual(payload["counts"]["commands"], 5)
        self.assertEqual(len(payload["demo_commands"]), 5)

    def test_demo_commands_are_all_parseable(self) -> None:
        for text in services.seed_demo_data()["demo_commands"]:
            with self.subTest(command=text):
                parsed = services.parse_command(text)
                self.assertNotEqual(parsed.commands[0].action, "unknown")

    def test_reset_clears_store(self) -> None:
        services.seed_demo_data()
        self.assertEqual(services.reset_demo_data()["status"], "ok")
        self.assertEqual(services.list_devices(), [])
        self.assertEqual(services.list_readings(), [])
        self.assertEqual(services.list_alerts(), [])


class UpdateDeviceStateTest(ServicesContractTest):
    def test_patch_status_and_state(self) -> None:
        light = self.add_light()
        updated = services.update_device_state(
            light.id,
            DeviceStateUpdate(status="online", state={"power": "on", "brightness": "70%"}),
        )
        self.assertEqual(updated.status, "online")
        self.assertEqual(updated.state["power"], "on")
        self.assertEqual(updated.state["brightness"], "70%")

    def test_patch_unknown_device_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            services.update_device_state("missing", DeviceStateUpdate(status="online"))


if __name__ == "__main__":
    unittest.main()
