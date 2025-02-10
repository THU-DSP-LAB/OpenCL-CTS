#!/bin/bash

# 文件夹列表
folders=(
    # "allocations"
    # "api"
    # "atomics"
    # "buffers"
    # "c11_atomics"
    # "commonfns"
    "conversions"
    # "events"
    # "generic_address_space"
    # "geometrics"
    # "integer_ops"
    # "math_brute_force"
    # "multiple_device_context"
    # "relationals"
    "select"
    # "subgroups"
    # "vectors"
    # "workgroups"
)

# 不遵循默认名称规律的文件夹与可执行文件的映射表
declare -A exec_map
exec_map=(
    ["math_brute_force"]="test_bruteforce"
    ["multiple_device_context"]="test_multiples"
)

# 遍历每个文件夹并在后台并行执行任务
for folder in "${folders[@]}"; do
    exec_file=${exec_map[$folder]:-"test_$folder"}
    (
        cd "build/test_conformance/$folder" && ./$exec_file | tee "1output_$folder.log"
    ) &  # 将每个任务放到后台
done

# 等待所有后台进程完成
wait
