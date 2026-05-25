from __future__ import annotations

import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections.abc import Mapping

from .executor import run_task
from .models import TestFailure, TestResult, TestTask
from .reporter import Reporter
from .state import StateRecorder


def run_tasks(
    tasks: list[TestTask],
    base_env: Mapping[str, str],
    max_workers: int,
    keep_pass_logs: bool,
    reporter: Reporter,
    state_recorder: StateRecorder,
) -> list[TestFailure]:
    failures: list[TestFailure] = []
    with ProcessPoolExecutor(max_workers=max_workers) as pool:
        future_to_task = {
            pool.submit(run_task, task, base_env): task
            for task in tasks
        }
        for future in as_completed(future_to_task):
            task = future_to_task[future]
            result = _collect_result(future, task, reporter)
            if isinstance(result, TestFailure):
                state_recorder.record_test_error(task, result.detail)
                failures.append(result)
                continue
            state_recorder.record_test_completed(result)
            failure = _report_result(result, keep_pass_logs, reporter)
            if failure is not None:
                failures.append(failure)
    return failures


def _collect_result(
    future,
    task: TestTask,
    reporter: Reporter,
) -> TestResult | TestFailure:
    try:
        return future.result()
    except Exception as error:
        detail = _format_exception(error)
        reporter.info(f"[ERROR ] {task.name} 异常: {error}")
        reporter.info(detail)
        return TestFailure(task.name, str(error))


def _report_result(
    result: TestResult,
    keep_pass_logs: bool,
    reporter: Reporter,
) -> TestFailure | None:
    for warning in result.warnings:
        reporter.info(f"[WARN  ] {result.name}: {warning}")

    if result.returncode == 0:
        reporter.info(f"[  OK  ] {result.name}")
        if not keep_pass_logs:
            _remove_pass_log(result, reporter)
        return None

    reporter.info(f"[ FAIL ] {result.name} (exit {result.returncode})")
    return TestFailure(result.name, str(result.returncode))


def _format_exception(error: BaseException) -> str:
    return "".join(
        traceback.format_exception(type(error), error, error.__traceback__)
    ).rstrip()


def _remove_pass_log(result: TestResult, reporter: Reporter) -> None:
    try:
        result.log_path.unlink()
    except OSError as error:
        reporter.info(
            f"[WARN  ] {result.name}: 删除通过日志失败 {result.log_path}: {error}"
        )
