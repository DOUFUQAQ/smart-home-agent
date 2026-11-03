"""``app.parser.parse_command_text`` 的行为断言。

这些用例同时充当"能力边界"文档：凡是标了 ``test_unsupported_*`` 的，
都是当前实现**做不到**的输入，断言它退化成 ``unknown`` 而不是瞎猜。
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

import tests  # noqa: F401  # 触发 sys.path 设置
from app.parser import (
    ACTION_CONDITIONAL_TURN_ON,
    ACTION_SET_BRIGHTNESS,
    ACTION_TURN_OFF,
    ACTION_TURN_ON,
    ACTION_UNKNOWN,
    normalize_text,
    parse_command_text,
)

PARSER_SOURCE = Path("backend") / "app" / "parser.py"


def parse(text: str) -> list[dict]:
    return parse_command_text(text)["commands"]


def actions(text: str) -> list[tuple[str, str]]:
    return [(item["action"], item["target"]) for item in parse(text)]


class NormalizeTextTest(unittest.TestCase):
    def test_strips_and_collapses_whitespace(self) -> None:
        self.assertEqual(normalize_text("  打开   客厅主灯  "), "打开 客厅主灯")

    def test_lowercases_ascii(self) -> None:
        self.assertEqual(normalize_text("Turn ON\tLight"), "turn on light")

    def test_chinese_characters_are_untouched(self) -> None:
        self.assertEqual(normalize_text("打开客厅主灯"), "打开客厅主灯")

    def test_normalized_text_is_returned_in_response(self) -> None:
        self.assertEqual(
            parse_command_text("  打开  客厅主灯 "),
            parse_command_text("打开 客厅主灯"),
        )


class ParseTurnOnOffTest(unittest.TestCase):
    def test_open_living_room_main_light(self) -> None:
        self.assertEqual(actions("打开客厅主灯"), [(ACTION_TURN_ON, "light")])

    def test_colloquial_open_light(self) -> None:
        self.assertEqual(actions("打开客厅灯"), [(ACTION_TURN_ON, "light")])

    def test_close_bedroom_socket(self) -> None:
        self.assertEqual(actions("关闭卧室插座"), [(ACTION_TURN_OFF, "socket")])

    def test_open_fan(self) -> None:
        self.assertEqual(actions("打开风扇"), [(ACTION_TURN_ON, "fan")])

    def test_open_air_conditioner(self) -> None:
        self.assertEqual(actions("打开空调"), [(ACTION_TURN_ON, "ac")])

    def test_lighting_synonym(self) -> None:
        # "照明" 也是 light 的关键词
        self.assertEqual(actions("打开照明"), [(ACTION_TURN_ON, "light")])

    def test_two_targets_in_one_sentence_keep_keyword_table_order(self) -> None:
        # 顺序来自 TARGET_KEYWORDS：light 在 fan 之前
        self.assertEqual(
            actions("打开风扇和灯"),
            [(ACTION_TURN_ON, "light"), (ACTION_TURN_ON, "fan")],
        )

    def test_contradictory_sentence_emits_both_actions(self) -> None:
        # 同一句里既打开又关闭 → 两条命令，执行时后一条覆盖前一条
        self.assertEqual(
            actions("打开灯然后关闭灯"),
            [(ACTION_TURN_ON, "light"), (ACTION_TURN_OFF, "light")],
        )


class ParseBrightnessTest(unittest.TestCase):
    def test_brighten_main_light(self) -> None:
        commands = parse("把客厅主灯调亮一点")
        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0]["action"], ACTION_SET_BRIGHTNESS)
        self.assertEqual(commands[0]["target"], "light")
        self.assertEqual(commands[0]["value"], "up")
        self.assertIsNone(commands[0]["condition"])

    def test_two_verbs_in_one_sentence(self) -> None:
        self.assertEqual(
            actions("请打开客厅主灯，再调亮一点"),
            [(ACTION_TURN_ON, "light"), (ACTION_SET_BRIGHTNESS, "light")],
        )

    def test_brightness_is_a_string_not_a_percentage(self) -> None:
        # 当前实现只会写 "up"，不理解"调到 60%"这类具体数值
        self.assertIsInstance(parse("把客厅主灯调亮一点")[0]["value"], str)


class ParseConditionalTest(unittest.TestCase):
    def test_conditional_fan_on(self) -> None:
        commands = parse("如果温度超过30度就打开风扇")
        self.assertEqual(len(commands), 2)
        self.assertEqual(commands[0]["action"], ACTION_TURN_ON)
        self.assertEqual(commands[0]["target"], "fan")
        self.assertEqual(commands[1]["action"], ACTION_CONDITIONAL_TURN_ON)
        self.assertEqual(commands[1]["target"], "fan")
        self.assertEqual(commands[1]["condition"], "temperature>30.0")
        # 条件值只体现在 condition 字符串里，value 保持 None
        self.assertIsNone(commands[1]["value"])

    def test_conditional_targets_ac_when_air_conditioner_mentioned(self) -> None:
        commands = parse("如果温度超过30度就打开空调")
        self.assertEqual(
            [(item["action"], item["target"]) for item in commands],
            [(ACTION_TURN_ON, "ac"), (ACTION_CONDITIONAL_TURN_ON, "ac")],
        )
        self.assertEqual(commands[1]["condition"], "temperature>30.0")

    def test_conditional_accepts_decimal_threshold(self) -> None:
        commands = parse("温度高于28.5度就打开风扇")
        conditional = [item for item in commands if item["action"] == ACTION_CONDITIONAL_TURN_ON]
        self.assertEqual(len(conditional), 1)
        self.assertEqual(conditional[0]["condition"], "temperature>28.5")

    def test_conditional_requires_turn_on_verb(self) -> None:
        # 只有条件、没有"打开/开启" → 不产出条件命令
        self.assertEqual(actions("温度超过30度"), [(ACTION_UNKNOWN, "unknown")])


class ParseUnsupportedTest(unittest.TestCase):
    """当前解析器不支持的输入，一律退化成 unknown（不瞎猜）。"""

    def test_unsupported_set_air_conditioner_temperature(self) -> None:
        # 任务书里的典型指令，但解析器只认"打开/关闭/调亮"三种动词
        self.assertEqual(actions("把卧室空调调到 26 度"), [(ACTION_UNKNOWN, "unknown")])

    def test_unsupported_temperature_query(self) -> None:
        # 没有查询类意图（问句不复存在），所以"温度多少"无法回答
        self.assertEqual(actions("客厅温度多少"), [(ACTION_UNKNOWN, "unknown")])

    def test_unsupported_short_verb_kai(self) -> None:
        # 口语"开灯"不含"打开/开启"，因此匹配失败
        self.assertEqual(actions("开灯"), [(ACTION_UNKNOWN, "unknown")])

    def test_unsupported_english_command(self) -> None:
        self.assertEqual(actions("turn on the light"), [(ACTION_UNKNOWN, "unknown")])

    def test_empty_string_is_unknown(self) -> None:
        self.assertEqual(actions(""), [(ACTION_UNKNOWN, "unknown")])


class ParseShapeTest(unittest.TestCase):
    def test_command_dict_has_exactly_four_keys(self) -> None:
        for command in parse("如果温度超过30度就打开风扇"):
            self.assertEqual(
                set(command),
                {"action", "target", "value", "condition"},
            )

    def test_response_has_normalized_text_and_commands(self) -> None:
        response = parse_command_text("打开客厅主灯")
        self.assertEqual(set(response), {"normalized_text", "commands"})
        self.assertEqual(response["normalized_text"], "打开客厅主灯")

    def test_always_at_least_one_command(self) -> None:
        for text in ("", "???", "随便说点什么", "打开客厅主灯"):
            self.assertGreaterEqual(len(parse(text)), 1)


class ParserDependencyGuardTest(unittest.TestCase):
    """确保解析层保持"零第三方依赖、零网络、零模型调用"。"""

    @staticmethod
    def _imported_top_level_modules() -> set[str]:
        tree = ast.parse((Path(tests.ROOT) / PARSER_SOURCE).read_text(encoding="utf-8"))
        modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                modules.add(node.module.split(".")[0])
        return modules

    def test_parser_module_imports_only_stdlib(self) -> None:
        # 白名单写死：只有标准和 typing 工具，没有 fastapi / pydantic /
        # requests / openai / 任何网络或模型 SDK。加依赖必须改这个测试。
        self.assertLessEqual(self._imported_top_level_modules(), {"__future__", "re", "typing"})

    def test_parser_module_does_not_touch_network(self) -> None:
        source = (Path(tests.ROOT) / PARSER_SOURCE).read_text(encoding="utf-8")
        for forbidden in ("urlopen", "requests.", "http://", "https://", "sk-"):
            self.assertNotIn(forbidden, source, f"parser.py 不应包含 {forbidden!r}")


if __name__ == "__main__":
    unittest.main()
