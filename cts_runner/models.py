from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CommandSpec:
    argv: tuple[str, ...]
    needs_single_thread: bool


@dataclass(frozen=True)
class TestMetadata:
    state: str | None


@dataclass(frozen=True)
class TestTask:
    suite: str
    subtest: str | None
    state: str | None
    command: tuple[str, ...]
    work_dir: Path
    log_path: Path
    needs_single_thread: bool
    cleanup_work_dir: bool

    @property
    def name(self) -> str:
        if self.subtest:
            return f"{self.suite}_{self.subtest}"
        return self.suite


@dataclass(frozen=True)
class TestResult:
    name: str
    returncode: int
    log_path: Path
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class TestFailure:
    name: str
    detail: str
