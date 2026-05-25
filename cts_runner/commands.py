from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from .errors import RunnerError
from .models import CommandSpec, TestMetadata, TestTask


COMMAND_SPECS: dict[str, CommandSpec] = {
    "math_brute_force": CommandSpec(("test_bruteforce",), True),
    "integer_ops": CommandSpec(("test_integer_ops",), True),
    "multiple_device_context": CommandSpec(("test_multiples",), False),
    "select": CommandSpec(("test_select", "-w"), False),
    "conversions": CommandSpec(("test_conversions", "-wz2"), False),
}


def build_tasks(
    suites: dict[str, dict[str, TestMetadata]],
    build_root: Path,
    logs_dir: Path,
    filter_states: Iterable[str],
) -> list[TestTask]:
    selected_states = set(filter_states)
    run_all = "all" in selected_states
    tasks: list[TestTask] = []

    if not build_root.is_dir():
        raise RunnerError(f"测试可执行文件根目录不存在: {build_root}")

    for suite, subtests in suites.items():
        spec = _command_spec_for_suite(suite)
        suite_dir = build_root / suite
        if not subtests:
            _validate_suite_executable(suite_dir, spec.argv[0])
            tasks.append(_build_suite_task(suite, spec, suite_dir, logs_dir))
            continue
        suite_tasks = _build_subtest_tasks(
            suite, spec, suite_dir, logs_dir, subtests, selected_states, run_all
        )
        if not suite_tasks:
            continue
        _validate_suite_executable(suite_dir, spec.argv[0])
        tasks.extend(suite_tasks)
    return tasks


def _command_spec_for_suite(suite: str) -> CommandSpec:
    return COMMAND_SPECS.get(suite, CommandSpec((f"test_{suite}",), False))


def _validate_suite_executable(suite_dir: Path, exe_name: str) -> None:
    if not suite_dir.is_dir():
        raise RunnerError(f"找不到测试 suite 目录: {suite_dir}")
    exe_path = suite_dir / exe_name
    if not exe_path.is_file():
        raise RunnerError(f"找不到测试可执行文件: {exe_path}")
    if not os.access(exe_path, os.X_OK):
        raise RunnerError(f"测试可执行文件不可执行: {exe_path}")


def _build_suite_task(
    suite: str,
    spec: CommandSpec,
    suite_dir: Path,
    logs_dir: Path,
) -> TestTask:
    command = (f"./{spec.argv[0]}", *spec.argv[1:])
    return TestTask(
        suite=suite,
        subtest=None,
        state=None,
        command=command,
        work_dir=suite_dir,
        log_path=logs_dir / f"output_{suite}.log",
        needs_single_thread=spec.needs_single_thread,
        cleanup_work_dir=False,
    )


def _build_subtest_tasks(
    suite: str,
    spec: CommandSpec,
    suite_dir: Path,
    logs_dir: Path,
    subtests: dict[str, TestMetadata],
    selected_states: set[str],
    run_all: bool,
) -> list[TestTask]:
    tasks: list[TestTask] = []
    for subtest, metadata in subtests.items():
        if not run_all and metadata.state not in selected_states:
            continue
        tasks.append(
            TestTask(
                suite=suite,
                subtest=subtest,
                state=metadata.state,
                command=(f"../{spec.argv[0]}", *spec.argv[1:], subtest),
                work_dir=suite_dir / subtest,
                log_path=logs_dir / f"output_{suite}_{subtest}.log",
                needs_single_thread=spec.needs_single_thread,
                cleanup_work_dir=True,
            )
        )
    return tasks
