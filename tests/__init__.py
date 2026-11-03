"""测试包：把 ``backend/`` 放进 ``sys.path``，让测试能 ``import app.parser``。

放在 ``tests/__init__.py`` 而不是只在 ``conftest.py`` 里，是因为
``python -m unittest discover -s tests -t .`` **不会**加载 conftest.py，
但 discover 会导入 ``tests`` 包本身。这样一来两种运行方式都能直接跑：

    python -m unittest discover -s tests -t .   # 标准库，零依赖
    python -m pytest -q                          # 装了 pytest 也行
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"

for _path in (BACKEND, ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
