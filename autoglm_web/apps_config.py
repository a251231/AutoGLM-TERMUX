from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from pprint import pformat
from typing import Dict, Tuple


def _autoglm_dir() -> Path:
    return Path(os.environ.get("AUTOGLM_DIR", str(Path.home() / "Open-AutoGLM"))).expanduser()


def apps_file() -> Path:
    return _autoglm_dir() / "phone_agent" / "config" / "apps.py"


def _extract_dict_legacy(text: str) -> Dict[str, str]:
    # 兼容性兜底：尝试解析 APP_PACKAGES = {...}
    m = re.search(r"APP_PACKAGES\\s*=\\s*(\\{.*?\\})", text, re.S)
    if not m:
        return {}
    body = m.group(1)
    try:
        data = ast.literal_eval(body)
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except Exception:
        return {}
    return {}


def _find_app_packages_value(tree: ast.AST) -> ast.AST | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "APP_PACKAGES":
                    return node.value
        if isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "APP_PACKAGES":
                return node.value
    return None


def _extract_dict_and_span(text: str) -> Tuple[Dict[str, str], tuple[int, int, int, int] | None]:
    try:
        tree = ast.parse(text)
    except Exception:
        return _extract_dict_legacy(text), None

    value = _find_app_packages_value(tree)
    if value is None:
        return _extract_dict_legacy(text), None

    data: Dict[str, str] = {}
    try:
        parsed = ast.literal_eval(value)
        if isinstance(parsed, dict):
            data = {str(k): str(v) for k, v in parsed.items()}
    except Exception:
        data = _extract_dict_legacy(text)

    span = None
    try:
        start_line = int(getattr(value, "lineno"))
        start_col = int(getattr(value, "col_offset"))
        end_line = int(getattr(value, "end_lineno"))
        end_col = int(getattr(value, "end_col_offset"))
        if start_line > 0 and end_line > 0:
            span = (start_line, start_col, end_line, end_col)
    except Exception:
        span = None

    return data, span


def load_app_packages() -> Dict[str, str]:
    path = apps_file()
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {}
    data, _ = _extract_dict_and_span(text)
    return data


def _index_from_line_col(lines: list[str], line: int, col: int) -> int:
    # line: 1-based, col: 0-based
    if line <= 1:
        return col
    return sum(len(lines[i]) for i in range(line - 1)) + col


def add_entries(entries: Dict[str, str]) -> Dict[str, str]:
    """
    将 entries 合并写入 Open-AutoGLM 的 apps.py 中的 APP_PACKAGES 字典。

    设计原则：
    - 不自动创建 Open-AutoGLM 目录，避免误写到错误路径
    - 尽量只替换 APP_PACKAGES 的字典字面量，保留文件其他内容
    """
    base = _autoglm_dir()
    if not base.exists():
        raise FileNotFoundError(f"未找到 Open-AutoGLM 目录: {base}")
    path = apps_file()
    if not path.exists():
        raise FileNotFoundError(f"未找到 apps.py: {path}")

    text = path.read_text(encoding="utf-8", errors="replace")
    data, span = _extract_dict_and_span(text)
    if span is None:
        raise RuntimeError("未在 apps.py 中定位到 APP_PACKAGES 字典，无法自动写入，请手动编辑")

    data.update({str(k): str(v) for k, v in entries.items()})

    formatted = pformat(data, width=100, sort_dicts=True)
    start_line, start_col, end_line, end_col = span
    indent = " " * max(start_col, 0)
    if "\n" in formatted:
        formatted = formatted.replace("\n", "\n" + indent)

    lines = text.splitlines(keepends=True)
    start = _index_from_line_col(lines, start_line, start_col)
    end = _index_from_line_col(lines, end_line, end_col)
    new_text = text[:start] + formatted + text[end:]

    path.write_text(new_text, encoding="utf-8")
    return data

