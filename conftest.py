"""pytest 入口：把 ``backend/`` 与仓库根放进 ``sys.path``。

这样两种运行方式都能直接用，不需要 `pip install -e .`：

    python -m unittest discover -s tests -t .    # 标准库，零第三方依赖
    python -m pytest -q                          # 装了 pytest 也行

核心测试（``tests/test_command_parser.py`` 等）只 import ``app.parser``，
那条导入链上没有 fastapi / pydantic，所以**没装任何第三方包也能全绿**。
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(ROOT, "backend")

for _path in (BACKEND, ROOT):
    if _path not in sys.path:
        sys.path.insert(0, _path)
