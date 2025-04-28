#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse

script_dir = os.path.dirname(os.path.abspath(__file__))

def run_test(folder, exec_file, subtest,
             build_root, logs_dir, orig_install_prefix):
    """
    在指定的子目录（若有 subtest 则是 build_root/folder/subtest，否则是 build_root/folder）里
    运行单个测试：
      1) 先复制一份 install_prefix 到 work_dir/install
      2) 设置独立环境变量
      3) 写 header 并执行测试，stdout+stderr 重定向到日志
      4) 测试结束后删除安装目录
    返回 (test_name, returncode)。
    """
    test_name = f"{folder}_{subtest}" if subtest else folder
    log_path  = os.path.join(logs_dir, f"output_{test_name}.log")

    # 1) 准备工作目录与命令
    if subtest:
        work_dir = os.path.join(build_root, folder, subtest)
        os.makedirs(work_dir, exist_ok=True)
        cmd = [f"../{exec_file}", subtest]
    else:
        work_dir = os.path.join(build_root, folder)
        cmd = [f"./{exec_file}"]

    if not os.path.isdir(work_dir):
        raise FileNotFoundError(f"找不到工作目录: {work_dir!r}")

    # 2) 验证源 install 路径是否存在
    if not os.path.isdir(orig_install_prefix):
        raise FileNotFoundError(
            f"原始 install 目录不存在: {orig_install_prefix!r}"
        )

    # 3) 复制 install_prefix 到 work_dir/install
    dest_prefix = os.path.join(work_dir, "install")
    # 如果残留就先删掉
    if os.path.exists(dest_prefix):
        shutil.rmtree(dest_prefix)
    try:
        # Python 3.8+ 可以加 dirs_exist_ok=True，否则如上先删除
        shutil.copytree(orig_install_prefix, dest_prefix)
    except Exception as e:
        # 既写到日志，又打印到终端
        errmsg = f"[ERROR] 拷贝 install 失败: {orig_install_prefix!r} -> {dest_prefix!r}: {e}"
        print(errmsg)
        with open(log_path, "a", encoding="utf-8") as log_file:
            log_file.write(errmsg + "\n")
        # 直接退出这一测例
        return test_name, -1

    # 4) 构造独立环境变量
    env = os.environ.copy()
    lib_dir = os.path.join(dest_prefix, "lib")
    old_ld = env.get("LD_LIBRARY_PATH", "")
    env["LD_LIBRARY_PATH"] = f"{lib_dir}:{old_ld}" if old_ld else lib_dir
    env["VENTUS_INSTALL_PREFIX"] = dest_prefix
    env["OCL_ICD_VENDORS"]   = os.path.join(lib_dir, "libpocl.so")
    env["CL_ICD_FILENAMES"]  = os.path.join(lib_dir, "libpocl.so")
    env["POCL_DEVICES"]      = "ventus"

    # 5) 写 header 并执行
    header = (
        f"在目录 {work_dir} 运行命令: {' '.join(cmd)}\n"
        f"源 install: {orig_install_prefix}\n目标 install: {dest_prefix}\n\n"
    )
    with open(log_path, "w", encoding="utf-8") as log_file:
        log_file.write(header)
        log_file.flush()
        proc = subprocess.run(
            cmd,
            cwd=work_dir,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
            env=env
        )

    # 6) 测试结束后删除临时 install 目录
    try:
        shutil.rmtree(dest_prefix)
    except Exception as e:
        print(f"[WARN] 无法删除临时 install 目录 {dest_prefix!r}: {e}")

    return test_name, proc.returncode


def main():
    parser = argparse.ArgumentParser(
        description="并行执行 OpenCL-CTS 测试并保存日志（每测例独立复制 install）"
    )
    parser.add_argument(
        "--json",
        default=os.path.join(script_dir, "test_list.json"),
        help="包含各测试套及子测例的 JSON 文件（默认为脚本同目录下的 test_list.json）"
    )
    parser.add_argument(
        "--build-root",
        default=os.path.join("build", "test_conformance"),
        help="测试可执行文件根目录（相对于脚本所在目录）"
    )
    parser.add_argument(
        "--logs-dir",
        default="logs",
        help="日志输出目录（会自动创建）"
    )
    parser.add_argument(
        "--ventus-install-prefix",
        default=os.environ.get("VENTUS_INSTALL_PREFIX"),
        help="原始 VENTUS_INSTALL_PREFIX 路径；可通过环境变量设置"
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=10,
        help="最大并发测试数量"
    )
    args = parser.parse_args()

    # 如果既没通过命令行，也没通过环境变量提供路径，则报错
    ventus_install_prefix = args.ventus_install_prefix
    if not ventus_install_prefix:
        parser.error(
            "必须通过 --ventus-install-prefix 或环境变量 VENTUS_INSTALL_PREFIX 提供安装路径"
        )
    # 统一为绝对路径，避免相对路径导致 copy 失败
    ventus_install_prefix = os.path.abspath(ventus_install_prefix)
    if not os.path.isdir(ventus_install_prefix):
        parser.error(f"VENTUS_INSTALL_PREFIX 路径不存在或不是目录: {ventus_install_prefix}")

    build_root    = os.path.abspath(os.path.join(script_dir, args.build_root))
    logs_dir      = os.path.abspath(os.path.join(script_dir, args.logs_dir))
    os.makedirs(logs_dir, exist_ok=True)

    # 1. Load JSON
    with open(args.json, "r", encoding="utf-8") as f:
        tests = json.load(f)

    # 2. 可执行文件映射（如有特殊命名）
    exec_map = {
        "math_brute_force": "test_bruteforce",
        "multiple_device_context": "test_multiples",
    }

    # 3. 构造任务列表
    tasks = []
    for folder, info in tests.items():
        exe      = exec_map.get(folder, f"test_{folder}")
        sub_list = info.get("test_list")
        if sub_list:
            for sub in sub_list:
                tasks.append((folder, exe, sub))
        else:
            tasks.append((folder, exe, None))

    total = len(tasks)
    print(f"准备执行 {total} 个测试任务，最大并发数 = {args.max_workers}\n")

    # 4. 并发执行并收集结果
    failures = []
    with ThreadPoolExecutor(max_workers=args.max_workers) as pool:
        future_to_task = {
            pool.submit(
                run_test,
                folder, exe, sub,
                build_root, logs_dir,
                ventus_install_prefix
            ): (folder, sub)
            for folder, exe, sub in tasks
        }
        for future in as_completed(future_to_task):
            folder, sub = future_to_task[future]
            name = f"{folder}_{sub}" if sub else folder
            try:
                _, code = future.result()
                if code == 0:
                    print(f"[  OK  ] {name}")
                else:
                    print(f"[ FAIL ] {name} (exit {code})")
                    failures.append((name, code))
            except Exception as e:
                print(f"[ERROR ] {name} 异常: {e}")
                failures.append((name, e))

    # 5. 汇总并退出
    if failures:
        print(f"\n共 {len(failures)} 项测试失败：")
        for name, err in failures:
            print(f"  - {name}: {err}")
        exit(1)
    else:
        print("\n所有测试通过！")


if __name__ == "__main__":
    main()
