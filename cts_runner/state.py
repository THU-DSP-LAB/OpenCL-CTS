from __future__ import annotations

import hashlib
import json
import sys
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .errors import RunnerError
from .models import TestResult, TestTask


BATCH_STARTED = "batch_started"
TEST_COMPLETED = "test_completed"
BATCH_FINISHED = "batch_finished"


@dataclass(frozen=True)
class CompletedTest:
    name: str
    returncode: int | None
    result: str
    log_path: str | None

    @property
    def failed(self) -> bool:
        return self.returncode != 0 or self.result == "error"


@dataclass(frozen=True)
class StateSnapshot:
    run_id: str | None
    config_hash: str | None
    task_count: int | None
    completed: Mapping[str, CompletedTest]
    finished: bool

    @property
    def incomplete(self) -> bool:
        return self.run_id is not None and not self.finished


@dataclass(frozen=True)
class ResumeDecision:
    run_id: str
    completed: Mapping[str, CompletedTest]
    resume: bool
    append_master_log: bool


class StateRecorder:
    def __init__(self, state_file: Path, run_id: str) -> None:
        self._state_file = state_file
        self._run_id = run_id

    @property
    def run_id(self) -> str:
        return self._run_id

    def record_test_completed(self, result: TestResult) -> None:
        payload = {
            "event": TEST_COMPLETED,
            "run_id": self._run_id,
            "name": result.name,
            "returncode": result.returncode,
            "result": "pass" if result.returncode == 0 else "fail",
            "log_path": str(result.log_path),
            "completed_at": _now_iso(),
        }
        append_state_event(self._state_file, payload)

    def record_test_error(self, task: TestTask, detail: str) -> None:
        payload = {
            "event": TEST_COMPLETED,
            "run_id": self._run_id,
            "name": task.name,
            "result": "error",
            "detail": detail,
            "completed_at": _now_iso(),
        }
        append_state_event(self._state_file, payload)

    def record_batch_finished(self, completed: Mapping[str, CompletedTest]) -> None:
        pass_count = sum(1 for item in completed.values() if item.returncode == 0)
        fail_count = sum(1 for item in completed.values() if item.failed)
        payload = {
            "event": BATCH_FINISHED,
            "run_id": self._run_id,
            "completed_at": _now_iso(),
            "pass": pass_count,
            "fail": fail_count,
        }
        append_state_event(self._state_file, payload)


def task_config_hash(
    json_path: Path,
    build_root: Path,
    filter_states: Sequence[str],
    tasks: Sequence[TestTask],
) -> str:
    digest = hashlib.sha256()
    digest.update(_file_hash(json_path).encode("utf-8"))
    payload = {
        "json_path": str(json_path),
        "build_root": str(build_root),
        "filter_states": list(filter_states),
        "tasks": [
            {
                "name": task.name,
                "suite": task.suite,
                "subtest": task.subtest,
                "state": task.state,
                "command": list(task.command),
            }
            for task in tasks
        ],
    }
    digest.update(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return digest.hexdigest()


def load_state_snapshot(state_file: Path) -> StateSnapshot:
    if not state_file.is_file():
        return StateSnapshot(None, None, None, {}, False)

    current_run_id: str | None = None
    config_hash: str | None = None
    task_count: int | None = None
    completed: dict[str, CompletedTest] = {}
    finished = False

    with state_file.open("r", encoding="utf-8") as file:
        for line_number, raw_line in enumerate(file, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as error:
                raise RunnerError(f"状态文件 JSONL 第 {line_number} 行损坏: {error}") from error
            if not isinstance(event, dict):
                raise RunnerError(f"状态文件 JSONL 第 {line_number} 行必须是 object")
            event_run_id = _optional_string(event.get("run_id"))
            if event.get("event") == BATCH_STARTED:
                completed.clear()
            current_run_id, config_hash, task_count, finished = _apply_batch_event(
                event, current_run_id, config_hash, task_count, finished
            )
            _apply_completed_event(event, current_run_id, event_run_id, completed)

    return StateSnapshot(current_run_id, config_hash, task_count, completed, finished)


def prepare_resume_decision(
    *,
    state_file: Path,
    snapshot: StateSnapshot,
    config_hash: str,
    task_count: int,
    force_resume: bool,
    force_fresh: bool,
) -> ResumeDecision:
    if force_fresh or snapshot.run_id is None or snapshot.finished:
        return _start_new_batch(state_file, config_hash, task_count)

    if snapshot.config_hash != config_hash:
        message = (
            f"状态文件属于不同批次，不能恢复: {state_file}\n"
            f"旧 config_hash: {snapshot.config_hash}\n"
            f"新 config_hash: {config_hash}"
        )
        if force_resume:
            raise RunnerError(message)
        raise RunnerError(message + "\n如需忽略旧状态，请使用 --fresh")

    if force_resume or _ask_resume(snapshot, task_count):
        return ResumeDecision(
            run_id=_require_run_id(snapshot),
            completed=snapshot.completed,
            resume=True,
            append_master_log=True,
        )
    return _start_new_batch(state_file, config_hash, task_count)


def append_state_event(state_file: Path, payload: Mapping[str, object]) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with state_file.open("a", encoding="utf-8") as file:
        file.write(json.dumps(dict(payload), sort_keys=True, separators=(",", ":")) + "\n")
        file.flush()


def _start_new_batch(state_file: Path, config_hash: str, task_count: int) -> ResumeDecision:
    run_id = uuid.uuid4().hex
    state_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "event": BATCH_STARTED,
        "run_id": run_id,
        "created_at": _now_iso(),
        "task_count": task_count,
        "config_hash": config_hash,
    }
    with state_file.open("w", encoding="utf-8") as file:
        file.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
        file.flush()
    return ResumeDecision(run_id, {}, False, False)


def _apply_batch_event(
    event: Mapping[str, object],
    run_id: str | None,
    config_hash: str | None,
    task_count: int | None,
    finished: bool,
) -> tuple[str | None, str | None, int | None, bool]:
    event_name = event.get("event")
    if event_name == BATCH_STARTED:
        return (
            _optional_string(event.get("run_id")),
            _optional_string(event.get("config_hash")),
            _optional_int(event.get("task_count")),
            False,
        )
    if event_name == BATCH_FINISHED and event.get("run_id") == run_id:
        return run_id, config_hash, task_count, True
    return run_id, config_hash, task_count, finished


def _apply_completed_event(
    event: Mapping[str, object],
    current_run_id: str | None,
    event_run_id: str | None,
    completed: dict[str, CompletedTest],
) -> None:
    if event.get("event") != TEST_COMPLETED or event_run_id != current_run_id:
        return
    name = _optional_string(event.get("name"))
    returncode = _optional_int(event.get("returncode"))
    result = _optional_string(event.get("result"))
    if name is None:
        return
    completed[name] = CompletedTest(
        name=name,
        returncode=returncode,
        result=result or _result_from_returncode(returncode),
        log_path=_optional_string(event.get("log_path")),
    )


def _ask_resume(snapshot: StateSnapshot, task_count: int) -> bool:
    completed_count = len(snapshot.completed)
    fail_count = sum(1 for item in snapshot.completed.values() if item.failed)
    if not sys.stdin.isatty():
        raise RunnerError(
            "检测到未完成的批量测试，但当前不是交互式终端；请使用 --resume 或 --fresh"
        )
    answer = input(
        f"检测到未完成的批量测试：已完成 {completed_count}/{task_count}，"
        f"其中失败 {fail_count} 项。是否恢复？[y/N] "
    )
    return answer.strip().lower() == "y"


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _optional_string(value: object) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _optional_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    return None


def _require_run_id(snapshot: StateSnapshot) -> str:
    if snapshot.run_id is None:
        raise RunnerError("状态文件缺少 run_id")
    return snapshot.run_id


def _result_from_returncode(returncode: int | None) -> str:
    if returncode == 0:
        return "pass"
    return "fail"
