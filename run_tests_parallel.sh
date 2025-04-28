#!/bin/bash

# 文件夹列表
folders=(
    "basic"
    "compiler"
    "api"
    "thread_dimensions"
    "commonfns"
    "computeinfo"
    "subgroups"
    "select"
    "buffers"
    "geometrics"
    "multiple_device_context"
    "events"
    "vectors"
    "printf"
    "conversions"
    "contractions"
    "integer_ops"
    "non_uniform_work_group"
    "generic_address_space"
    "math_brute_force"
    "atomics"
    "c11_atomics"
    "pipes"
    "SVM"
    "device_execution"
    "workgroups"
    "mem_host_flags"
    "relationals"
    "profiling"
    "allocations"
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
