"""告警规则断言（``app.parser.detect_alerts``）。

阈值语义：**严格大于**才告警，等于阈值不告警；每个超限指标各产生一条，
温度在前、气体在后（顺序与 ``services.evaluate_alerts`` 输出一致）。
"""

from __future__ import annotations

import unittest

import tests  # noqa: F401  # 触发 sys.path 设置
from app.parser import GAS_THRESHOLD, TEMP_THRESHOLD, detect_alerts


class ThresholdValueTest(unittest.TestCase):
    def test_documented_thresholds(self) -> None:
        self.assertEqual(TEMP_THRESHOLD, 30.0)
        self.assertEqual(GAS_THRESHOLD, 300.0)


class TemperatureAlertTest(unittest.TestCase):
    def test_below_threshold_has_no_alert(self) -> None:
        self.assertEqual(detect_alerts(24.6, None), [])

    def test_exactly_at_threshold_has_no_alert(self) -> None:
        # 严格大于：30.0 不告警
        self.assertEqual(detect_alerts(30.0, None), [])

    def test_above_threshold_warns(self) -> None:
        alerts = detect_alerts(30.1, None)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["level"], "warning")
        self.assertEqual(alerts[0]["message"], "温度过高: 30.1°C")

    def test_integral_float_is_formatted_with_decimal(self) -> None:
        # 直接用 f-string 插值 float，所以 31.0 会显示成 "31.0°C"
        self.assertEqual(detect_alerts(31.0, None)[0]["message"], "温度过高: 31.0°C")

    def test_missing_temperature_is_skipped(self) -> None:
        self.assertEqual(detect_alerts(None, 100.0), [])


class GasAlertTest(unittest.TestCase):
    def test_below_threshold_has_no_alert(self) -> None:
        self.assertEqual(detect_alerts(None, 135.0), [])

    def test_exactly_at_threshold_has_no_alert(self) -> None:
        self.assertEqual(detect_alerts(None, 300.0), [])

    def test_above_threshold_is_critical(self) -> None:
        alerts = detect_alerts(None, 300.1)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["level"], "critical")
        self.assertEqual(alerts[0]["message"], "可燃气体浓度异常: 300.1 ppm")

    def test_missing_gas_is_skipped(self) -> None:
        self.assertEqual(detect_alerts(24.6, None), [])


class CombinedAlertTest(unittest.TestCase):
    def test_both_metrics_above_threshold(self) -> None:
        alerts = detect_alerts(34.2, 450.0)
        self.assertEqual(len(alerts), 2)
        self.assertEqual([item["level"] for item in alerts], ["warning", "critical"])

    def test_nothing_reported(self) -> None:
        self.assertEqual(detect_alerts(None, None), [])

    def test_custom_thresholds_are_honoured(self) -> None:
        self.assertEqual(detect_alerts(26.0, 26.0, temp_threshold=30.0, gas_threshold=30.0), [])
        self.assertEqual(len(detect_alerts(31.0, 31.0, temp_threshold=30.0, gas_threshold=30.0)), 2)

    def test_alert_dict_has_level_and_message_only(self) -> None:
        for alert in detect_alerts(34.2, 450.0):
            self.assertEqual(set(alert), {"level", "message"})


class DemoSeedConsistencyTest(unittest.TestCase):
    """用 seed 数据里的六条读数反推告警条数（与 ``/api/demo/seed`` 的 counts.alerts 对齐）。"""

    DEMO_READINGS = [
        (24.6, 78.0),
        (26.3, 96.0),
        (28.7, 135.0),
        (31.2, 180.0),
        (32.4, 338.0),
        (29.5, 120.0),
    ]

    def test_seed_readings_produce_three_alerts(self) -> None:
        # (31.2, 180) → 温度告警 1 条；(32.4, 338) → 温度 + 气体共 2 条
        total = sum(len(detect_alerts(temp, gas)) for temp, gas in self.DEMO_READINGS)
        self.assertEqual(total, 3)

    def test_only_fourth_and_fifth_readings_alert(self) -> None:
        per_reading = [len(detect_alerts(temp, gas)) for temp, gas in self.DEMO_READINGS]
        self.assertEqual(per_reading, [0, 0, 0, 1, 2, 0])


if __name__ == "__main__":
    unittest.main()
