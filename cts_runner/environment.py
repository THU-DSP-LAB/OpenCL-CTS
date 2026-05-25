from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Mapping

from .errors import RunnerError


REQUIRED_ENV_KEYS = (
    "VENTUS_INSTALL_PREFIX",
    "LD_LIBRARY_PATH",
    "POCL_DEVICES",
    "OCL_ICD_VENDORS",
)


def load_ventus_env(
    env_script: Path,
    ventus_install_prefix: Path | None,
    base_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    if not env_script.is_file():
        raise RunnerError(f"env.sh 不存在: {env_script}")

    source_env = dict(os.environ if base_env is None else base_env)
    if ventus_install_prefix is not None:
        source_env["VENTUS_INSTALL_PREFIX"] = str(ventus_install_prefix)

    proc = subprocess.run(
        ["bash", "-c", 'source "$1" >/dev/null && env -0', "bash", str(env_script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=source_env,
        check=False,
    )
    if proc.returncode != 0:
        stderr = proc.stderr.decode(errors="replace").strip()
        raise RunnerError(f"加载 env.sh 失败: {env_script}\n{stderr}")

    loaded_env = _parse_env_output(proc.stdout)
    _validate_ventus_env(loaded_env)
    return loaded_env


def _parse_env_output(output: bytes) -> dict[str, str]:
    env: dict[str, str] = {}
    for item in output.split(b"\0"):
        if not item:
            continue
        key, separator, value = item.partition(b"=")
        if not separator:
            raise RunnerError("env.sh 输出了非法环境变量项")
        env[key.decode(errors="surrogateescape")] = value.decode(
            errors="surrogateescape"
        )
    return env


def _validate_ventus_env(env: Mapping[str, str]) -> None:
    missing = [key for key in REQUIRED_ENV_KEYS if not env.get(key)]
    if missing:
        raise RunnerError(f"env.sh 未设置必要环境变量: {', '.join(missing)}")

    prefix = Path(env["VENTUS_INSTALL_PREFIX"])
    if not prefix.is_dir():
        raise RunnerError(f"VENTUS_INSTALL_PREFIX 不存在或不是目录: {prefix}")

    libpocl = prefix / "lib" / "libpocl.so"
    if not libpocl.is_file():
        raise RunnerError(f"找不到 Ventus PoCL 库: {libpocl}")
