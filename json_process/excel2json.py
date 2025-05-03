#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import pandas as pd

# ========== 全局配置 ==========
base_dir   = os.path.dirname(__file__)
# EXCEL_FILE = os.path.join(base_dir, 'ventus进展-20231129.xls')
EXCEL_FILE = os.path.join(base_dir, 'ventus进展-20240429.xls')
# SHEET_MAP  = {
#     1: "basic",
#     2: "compiler",
#     3: "api",
#     4: "thread_dimensions",
#     5: "commonfns",
#     6: "computeinfo",
# }
SHEET_MAP  = {
    4: "subgroups",
    5: "select",
    6: "buffers",
    7: "geometrics",
    8: "multiple_device_context",
    9: "events",
    10: "vectors",
    11: "printf",
    12: "conversions",
    13: "contractions",
    14: "integer_ops",
    15: "non_uniform_work_group",
    16: "generic_address_space",
    18: "math_brute_force",
    19: "atomics",
    20: "c11_atomics",
    21: "pipes",
    22: "SVM",
    23: "device_execution",
    24: "workgroups",
    25: "mem_host_flags",
    26: "relationals",
    27: "profiling",
    28: "allocations",
}
VALID_STATES = {"pass", "passed", "fail", "skip", "unsupport"}
OUTPUT_FILE  = os.path.join(base_dir, 'test_results2.json')
# ============================

def choose_engine(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == '.xls':
        return 'xlrd'
    elif ext == '.xlsx':
        return 'openpyxl'
    else:
        # 其他格式交给 pandas 自动选择
        return None

def process_sheet(sheet_idx: int, suite_name: str) -> dict:
    zero_based = sheet_idx - 1
    engine = choose_engine(EXCEL_FILE)
    try:
        read_kwargs = dict(sheet_name=zero_based, header=None)
        if engine:
            read_kwargs['engine'] = engine
        df = pd.read_excel(EXCEL_FILE, **read_kwargs)
    except Exception as e:
        sys.exit(f"Error: 无法读取 '{EXCEL_FILE}' 的第 {sheet_idx} 个工作表，使用引擎 {engine!r}：{e}")

    print(f">> 开始处理工作表 #{sheet_idx} ：'{suite_name}'")

    results = {}

    for _, row in df.iterrows():
        test_name  = row.iloc[1]
        status_raw = row.iloc[2]

        if pd.isna(test_name) or pd.isna(status_raw):
            continue

        name   = str(test_name).strip()
        status = str(status_raw).strip().lower()

        if status not in VALID_STATES:
            print(f"Warning: 忽略无效对子：({name!r}, {status_raw!r})")
            continue

        results[name] = {
            "state":   status,
            "comment": ""
        }

    return {suite_name: results}


def main():
    if not os.path.isfile(EXCEL_FILE):
        sys.exit(f"Error: 找不到 Excel 文件 '{EXCEL_FILE}'")

    all_suites = {}
    for idx, suite in SHEET_MAP.items():
        all_suites.update(process_sheet(idx, suite))

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_suites, f, indent=4, ensure_ascii=False)

    print(f"已生成：{OUTPUT_FILE}")

if __name__ == '__main__':
    main()