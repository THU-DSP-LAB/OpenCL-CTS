#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
import argparse

script_dir = os.path.dirname(os.path.abspath(__file__))

def run_test(folder, exec_file, subtest,
             build_root, logs_dir, install_queue):
    """
    在指定的子目录（若有 subtest 则是 build_root/folder/subtest，否则是 build_root/folder）里
    运行单个测试：
      1) 每次从 install_queue 中取出一个 install 副本，运行测试后归还
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

    # 2) 从队列取一个 install 副本
    install_prefix = install_queue.get()

    try:
        # 3) 构造独立环境变量
        env = os.environ.copy()
        lib_dir = os.path.join(install_prefix, "lib")
        old_ld = env.get("LD_LIBRARY_PATH", "")
        env["LD_LIBRARY_PATH"]      = f"{lib_dir}:{old_ld}" if old_ld else lib_dir
        env["VENTUS_INSTALL_PREFIX"] = install_prefix
        env["OCL_ICD_VENDORS"]       = os.path.join(lib_dir, "libpocl.so")
        env["CL_ICD_FILENAMES"]      = os.path.join(lib_dir, "libpocl.so")
        env["POCL_DEVICES"]          = "ventus"

        # 4) 写 header 并执行
        header = (
            f"在目录 {work_dir} 运行命令: {' '.join(cmd)}\n"
            f"使用 install 副本: {install_prefix}\n\n"
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

        return test_name, proc.returncode

    finally:
        # 5) 归还该 install 副本
        install_queue.put(install_prefix)


def main():
    parser = argparse.ArgumentParser(
        description="并行执行 OpenCL-CTS 测试并保存日志（预先复制 install 副本池）"
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
    ventus_install_prefix = os.path.abspath(ventus_install_prefix)
    if not os.path.isdir(ventus_install_prefix):
        parser.error(f"VENTUS_INSTALL_PREFIX 路径不存在或不是目录: {ventus_install_prefix}")

    # 准备 build_root 和 logs_dir 的绝对路径
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

    # 4. 预先复制 install 副本池
    installs_base = os.path.join(script_dir, "build", "installs")
    # 如果已存在，就先删除再重建
    if os.path.isdir(installs_base):
        shutil.rmtree(installs_base)
    os.makedirs(installs_base, exist_ok=True)
    install_paths = []
    for i in range(args.max_workers):
        dest = os.path.join(installs_base, f"install_{i}")
        shutil.copytree(ventus_install_prefix, dest)
        install_paths.append(dest)

    # 5. 构造线程安全的 install 副本队列
    install_queue = Queue()
    for path in install_paths:
        install_queue.put(path)

    # 6. 并发执行并收集结果
    failures = []
    with ThreadPoolExecutor(max_workers=args.max_workers) as pool:
        future_to_task = {
            pool.submit(
                run_test,
                folder, exe, sub,
                build_root, logs_dir,
                install_queue
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

    # 7. 汇总并退出
    if failures:
        print(f"\n共 {len(failures)} 项测试失败：")
        for name, err in failures:
            print(f"  - {name}: {err}")
        exit(1)
    else:
        print("\n所有测试通过！")


if __name__ == "__main__":
    main()
