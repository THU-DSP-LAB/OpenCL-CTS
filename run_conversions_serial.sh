#!/bin/bash

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

# 清空日志文件
> "$log_file"

# 定义格式类型
formats=("uchar" "char" "ushort" "short" "uint" "int" "float" "double" "ulong" "long")
saturations=("" "_sat")
roundings=("" "_rte" "_rtp" "_rtn" "_rtz")

# 生成并运行测试命令
for dest in "${formats[@]}"; do
    for sat in "${saturations[@]}"; do
        for round in "${roundings[@]}"; do
            for src in "${formats[@]}"; do
                test_name="${dest}${sat}${round}_${src}"
                cmd="./$test_exec $test_name"
                
                echo "Running: $cmd" | tee -a "$log_file"
                
                # 运行命令，获取完整输出
                output=$($cmd 2>&1 | tee /dev/tty)

                # 查找包含 "PASSED test" 的行（不要求整行匹配）
                matched_lines=$(echo "$output" | grep -i "PASSED test")

                if [ -n "$matched_lines" ]; then
                    while IFS= read -r line; do
                        echo "$cmd: $line" | tee -a "$log_file"
                    done <<< "$matched_lines"
                else
                    echo "$cmd: No 'PASSED test' found" | tee -a "$log_file"
                fi
            done
        done
    done
done

echo "All tests completed. Results saved in $test_dir/$log_file."
