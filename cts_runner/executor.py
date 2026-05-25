from __future__ import annotations

import shutil
import subprocess
from collections.abc import Mapping

from .models import TestResult, TestTask


def run_task(task: TestTask, base_env: Mapping[str, str]) -> TestResult:
    _prepare_work_dir(task)
    env = dict(base_env)
    if task.needs_single_thread:
        env["CL_TEST_SINGLE_THREADED"] = "1"

    warnings: list[str] = []
    returncode: int | None = None
    try:
        task.log_path.parent.mkdir(parents=True, exist_ok=True)
        with task.log_path.open("w", encoding="utf-8") as log_file:
            log_file.write(_log_header(task))
            log_file.flush()
            proc = subprocess.run(
                list(task.command),
                cwd=task.work_dir,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
                check=False,
            )
        returncode = proc.returncode
    finally:
        if task.cleanup_work_dir:
            try:
                shutil.rmtree(task.work_dir)
            except OSError as error:
                warnings.append(f"删除子测例目录失败 {task.work_dir}: {error}")
    if returncode is None:
        raise RuntimeError(f"测试未返回退出码: {task.name}")
    return TestResult(
        name=task.name,
        returncode=returncode,
        log_path=task.log_path,
        warnings=tuple(warnings),
    )


def _prepare_work_dir(task: TestTask) -> None:
    if task.cleanup_work_dir:
        task.work_dir.parent.mkdir(parents=False, exist_ok=True)
        task.work_dir.mkdir(exist_ok=True)
        return
    if not task.work_dir.is_dir():
        raise FileNotFoundError(f"找不到工作目录: {task.work_dir}")


def _log_header(task: TestTask) -> str:
    command = " ".join(task.command)
    return f"在目录 {task.work_dir} 运行命令: {command}\n\n"
