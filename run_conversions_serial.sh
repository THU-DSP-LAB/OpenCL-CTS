#!/bin/bash

# This script runs all test cases for "test_conversions" in sequence and logs the results.
# It supports resuming from a specified test case to continue from the last interruption.
# 
# Usage:
#   ./run_conversions_serial.sh              # Run all tests from the beginning
#   ./run_conversions_serial.sh uchar_uint   # Resume from "uchar_uint" and continue testing
# 
# Logs:
#   - The log file "1test_conversions.log" is appended, not overwritten.
#   - Each test run is prefixed with "===== Starting new test session from: XXX =====".
#   - The output of "test_conversions" is logged, including whether "PASSED test" is found.
#   - Each individual test has its own log file with full output.

# 定义测试目录
test_dir="build/test_conformance/conversions"
test_exec="test_conversions"
log_file="1test_conversions.log"

# 确保目录存在
if [ ! -d "$test_dir" ]; then
    echo "Error: Directory $test_dir does not exist."
    exit 1
fi

# 进入测试目录
cd "$test_dir" || exit 1

# 获取用户指定的起始测试名称（如果提供）
start_test="$1"

# If no start test name is provided, clear the log file; otherwise, append
if [ -z "$start_test" ]; then
    echo "===== Starting new test session: FULL RUN =====" > "$log_file"
else
    echo "===== Starting new test session from: $start_test =====" >> "$log_file"
fi

# 定义格式类型
formats=("uchar" "char" "ushort" "short" "uint" "int" "float" "double" "ulong" "long")
saturations=("" "_sat")
roundings=("" "_rte" "_rtp" "_rtn" "_rtz")

# 标记是否开始执行（用于断点续测）
start_flag=false

# 生成并运行测试命令
for dest in "${formats[@]}"; do
    for sat in "${saturations[@]}"; do
        for round in "${roundings[@]}"; do
            for src in "${formats[@]}"; do
                test_name="${dest}${sat}${round}_${src}"
                cmd="./$test_exec $test_name"
                
                # 如果指定了起点，且还未到指定的起始测试名称，则跳过
                if [ -n "$start_test" ] && [ "$start_flag" = false ]; then
                    if [ "$test_name" == "$start_test" ]; then
                        start_flag=true
                    else
                        continue
                    fi
                fi

                test_log_file="1test_${test_name}.log"
                echo "Running: $cmd" | tee -a "$log_file" "$test_log_file"
                
                # 运行命令，获取完整输出
                output=$($cmd 2>&1 | tee -a "$test_log_file")

                # 查找包含 "PASSED test" 的行（不要求整行匹配）
                matched_lines=$(echo "$output" | grep -i "PASSED test")

                if [ -n "$matched_lines" ]; then
                    while IFS= read -r line; do
                        echo "$cmd: $line" | tee -a "$log_file" "$test_log_file"
                    done <<< "$matched_lines"
                else
                    echo "$cmd: No 'PASSED test' found" | tee -a "$log_file" "$test_log_file"
                fi
            done
        done
    done
done

echo "All tests completed. Results saved in $test_dir/$log_file."
