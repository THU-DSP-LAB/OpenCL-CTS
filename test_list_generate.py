#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import re
import json

def convert_test_list(text):
    """
    将所有 "test_list": [a, b, c, ...] 中的元素转换为 JSON 字符串：
    -> "test_list": ["a", "b", "c", ...]
    """
    pattern = re.compile(r'("test_list"\s*:\s*)\[(.*?)\]', re.DOTALL)
    def repl(match):
        prefix = match.group(1)
        items_str = match.group(2)
        # 拆分、去重空白并加引号
        items = [item.strip() for item in items_str.split(',') if item.strip()]
        quoted = ', '.join(json.dumps(item) for item in items)
        return f'{prefix}[{quoted}]'
    return pattern.sub(repl, text)

def main():
    # 输入、输出文件路径
    base_dir = os.path.dirname(__file__)
    input_path  = os.path.join(base_dir, 'test_list.json.text')
    output_path = os.path.join(base_dir, 'test_list.json')

    # 读取原始文件
    with open(input_path, 'r', encoding='utf-8') as f:
        raw_text = f.read()

    # 转换 test_list 数组
    fixed_text = convert_test_list(raw_text)

    # 验证并解析为 Python 对象
    data = json.loads(fixed_text)

    # 写出格式化后的 JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

if __name__ == '__main__':
    main()
