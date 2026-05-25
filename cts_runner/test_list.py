from __future__ import annotations

import json
from pathlib import Path

from .errors import RunnerError
from .models import TestMetadata


TestSuites = dict[str, dict[str, TestMetadata]]


def load_test_suites(json_path: Path) -> TestSuites:
    if not json_path.is_file():
        raise RunnerError(f"测试列表 JSON 不存在: {json_path}")

    with json_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise RunnerError("测试列表 JSON 顶层必须是 object")

    suites: TestSuites = {}
    for suite, subtests in data.items():
        if not isinstance(suite, str):
            raise RunnerError("测试 suite 名称必须是字符串")
        suites[suite] = _parse_subtests(suite, subtests)
    return suites


def _parse_subtests(suite: str, subtests: object) -> dict[str, TestMetadata]:
    if not subtests:
        return {}
    if not isinstance(subtests, dict):
        raise RunnerError(f"{suite}: 子测例列表必须是 object")

    parsed: dict[str, TestMetadata] = {}
    for name, metadata in subtests.items():
        if not isinstance(name, str):
            raise RunnerError(f"{suite}: 子测例名称必须是字符串")
        if not isinstance(metadata, dict):
            raise RunnerError(f"{suite}.{name}: metadata 必须是 object")
        state = metadata.get("state")
        if state is not None and not isinstance(state, str):
            raise RunnerError(f"{suite}.{name}: state 必须是字符串")
        parsed[name] = TestMetadata(state=state)
    return parsed
