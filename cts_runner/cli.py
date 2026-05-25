from __future__ import annotations

import sys
from collections.abc import Sequence

from .commands import build_tasks
from .config import parse_args
from .environment import load_ventus_env
from .errors import RunnerError
from .reporter import Reporter
from .runner import run_tasks
from .state import (
    CompletedTest,
    StateRecorder,
    load_state_snapshot,
    prepare_resume_decision,
    task_config_hash,
)
from .test_list import load_test_suites


def main(argv: Sequence[str] | None = None) -> int:
    try:
        config = parse_args(argv)
        suites = load_test_suites(config.json_path)
        tasks = build_tasks(
            suites,
            config.build_root,
            config.logs_dir,
            config.filter_states,
        )
        state_decision = prepare_resume_decision(
            state_file=config.state_file,
            snapshot=load_state_snapshot(config.state_file),
            config_hash=task_config_hash(
                config.json_path,
                config.build_root,
                config.filter_states,
                tasks,
            ),
            task_count=len(tasks),
            force_resume=config.resume,
            force_fresh=config.fresh,
        )
        with Reporter(
            config.master_log_path,
            append=state_decision.append_master_log,
        ) as reporter:
            return _run(config, reporter, tasks, state_decision)
    except RunnerError as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        return 2


def _run(config, reporter: Reporter, tasks, state_decision) -> int:
    base_env = load_ventus_env(
        config.env_script,
        config.ventus_install_prefix,
    )
    completed = dict(state_decision.completed)
    pending_tasks = _pending_tasks(tasks, completed)

    reporter.info(
        f"准备执行 {len(pending_tasks)} 个测试任务，总任务数 = {len(tasks)}，最大并发数 = {config.max_workers}"
    )
    reporter.info(f"状态文件: {config.state_file}")
    if state_decision.resume:
        reporter.info(f"恢复批次: {state_decision.run_id}，已完成 {len(completed)} 项")
    else:
        reporter.info(f"新批次: {state_decision.run_id}")
    reporter.info(f"使用 env.sh: {config.env_script}")
    reporter.info(f"使用 VENTUS_INSTALL_PREFIX: {base_env['VENTUS_INSTALL_PREFIX']}")
    reporter.info()

    state_recorder = StateRecorder(config.state_file, state_decision.run_id)
    run_tasks(
        pending_tasks,
        base_env,
        config.max_workers,
        config.keep_pass_logs,
        reporter,
        state_recorder,
    )
    final_snapshot = load_state_snapshot(config.state_file)
    all_completed = dict(final_snapshot.completed)
    missing = [task.name for task in tasks if task.name not in all_completed]
    if missing:
        raise RunnerError(
            f"状态文件缺少 {len(missing)} 个测例完成记录，批次未完成"
        )
    state_recorder.record_batch_finished(all_completed)
    return _finish(_failed_tests(all_completed), reporter)


def _pending_tasks(tasks, completed: dict[str, CompletedTest]):
    return [task for task in tasks if task.name not in completed]


def _failed_tests(completed: dict[str, CompletedTest]) -> dict[str, CompletedTest]:
    return {
        name: item
        for name, item in completed.items()
        if item.failed
    }


def _finish(failures: dict[str, CompletedTest], reporter: Reporter) -> int:
    if failures:
        reporter.info(f"\n共 {len(failures)} 项测试失败：")
        for failure in failures.values():
            reporter.info(f"  - {failure.name}: {_failure_detail(failure)}")
        return 1

    reporter.info("\n所有测试通过！")
    return 0


def _failure_detail(failure: CompletedTest) -> str:
    if failure.returncode is None:
        return failure.result
    return str(failure.returncode)
