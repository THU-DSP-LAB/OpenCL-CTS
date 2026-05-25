from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


SCRIPT_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SCRIPT_DIR.parent
VALID_STATES = ("all", "pass", "fail", "skip", "unsupport")


@dataclass(frozen=True)
class RunnerConfig:
    script_dir: Path
    json_path: Path
    build_root: Path
    logs_dir: Path
    env_script: Path
    ventus_install_prefix: Path | None
    max_workers: int
    filter_states: tuple[str, ...]
    keep_pass_logs: bool
    master_log: str
    state_file: Path
    resume: bool
    fresh: bool

    @property
    def master_log_path(self) -> Path:
        return self.logs_dir / self.master_log


def parse_args(argv: Sequence[str] | None = None) -> RunnerConfig:
    parser = argparse.ArgumentParser(
        description="并行执行 Ventus OpenCL-CTS 测试并保存日志"
    )
    parser.add_argument(
        "--json",
        default=str(SCRIPT_DIR / "test_list_new.json"),
        help="包含各测试套及子测例的 JSON 文件",
    )
    parser.add_argument(
        "--build-root",
        default="build/test_conformance",
        help="测试可执行文件根目录（相对于 OpenCL-CTS 目录）",
    )
    parser.add_argument(
        "--logs-dir",
        default="logs",
        help="日志输出目录（相对于 OpenCL-CTS 目录，会自动创建）",
    )
    parser.add_argument(
        "--env-sh",
        default=str(REPO_ROOT / "env.sh"),
        help="用于设置 Ventus 运行环境的 env.sh 路径",
    )
    parser.add_argument(
        "--ventus-install-prefix",
        default=None,
        help="传给 env.sh 的 VENTUS_INSTALL_PREFIX；默认使用当前环境或 env.sh 默认值",
    )
    parser.add_argument(
        "--max-workers",
        type=_positive_int,
        default=5,
        help="最大并发测试数量",
    )
    parser.add_argument(
        "--filter-state",
        nargs="+",
        choices=VALID_STATES,
        default=("pass", "skip", "unsupport"),
        help=(
            "运行指定状态的子测例，可一次指定多个，如 "
            "'--filter-state pass unsupport'；使用 'all' 跳过过滤。"
            "默认运行 pass, skip, unsupport"
        ),
    )
    parser.add_argument(
        "--keep-pass-logs",
        action="store_true",
        help="保留通过的子测例日志；默认删除",
    )
    parser.add_argument(
        "--master-log",
        default="all_run_tests.log",
        help="主日志文件名，将保存在 logs-dir 目录下",
    )
    parser.add_argument(
        "--state-file",
        default="logs/run_state.jsonl",
        help="断点续跑状态文件路径（相对于 OpenCL-CTS 目录）",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--resume",
        action="store_true",
        help="检测到未完成批次时直接恢复，不交互询问",
    )
    mode_group.add_argument(
        "--fresh",
        action="store_true",
        help="忽略已有状态文件并开始新批次，不交互询问",
    )
    args = parser.parse_args(argv)

    return RunnerConfig(
        script_dir=SCRIPT_DIR,
        json_path=_resolve_path(args.json),
        build_root=_resolve_from_script_dir(args.build_root),
        logs_dir=_resolve_from_script_dir(args.logs_dir),
        env_script=_resolve_path(args.env_sh),
        ventus_install_prefix=_optional_path(args.ventus_install_prefix),
        max_workers=args.max_workers,
        filter_states=tuple(args.filter_state),
        keep_pass_logs=args.keep_pass_logs,
        master_log=args.master_log,
        state_file=_resolve_from_script_dir(args.state_file),
        resume=args.resume,
        fresh=args.fresh,
    )


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("必须是正整数")
    return parsed


def _resolve_from_script_dir(value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return SCRIPT_DIR / path


def _resolve_path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def _optional_path(value: str | None) -> Path | None:
    if value is None:
        return None
    return _resolve_path(value)
