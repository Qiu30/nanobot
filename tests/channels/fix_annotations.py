#!/usr/bin/env python3
"""
批量添加 'from __future__ import annotations' 到 Python 文件

用于解决 Python 3.9 与新类型注解语法的兼容性问题
"""

import os
import sys
from pathlib import Path


def add_future_import(file_path: Path) -> bool:
    """
    在 Python 文件开头添加 from __future__ import annotations

    Returns:
        True if file was modified, False otherwise
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 检查是否已经有这个 import
        if 'from __future__ import annotations' in content:
            print(f"⏭️  跳过（已存在）: {file_path}")
            return False

        lines = content.split('\n')

        # 找到插入位置（在 docstring 之后，第一个 import 之前）
        insert_pos = 0
        in_docstring = False
        docstring_char = None

        for i, line in enumerate(lines):
            stripped = line.strip()

            # 跳过空行和注释
            if not stripped or stripped.startswith('#'):
                continue

            # 处理 docstring
            if not in_docstring:
                if stripped.startswith('"""') or stripped.startswith("'''"):
                    docstring_char = stripped[:3]
                    if stripped.count(docstring_char) >= 2:
                        # 单行 docstring
                        insert_pos = i + 1
                        continue
                    else:
                        # 多行 docstring 开始
                        in_docstring = True
                        continue
            else:
                if docstring_char in line:
                    # 多行 docstring 结束
                    in_docstring = False
                    insert_pos = i + 1
                    continue

            # 找到第一个非 docstring 的内容
            if not in_docstring:
                insert_pos = i
                break

        # 插入 import
        new_lines = lines[:insert_pos]
        new_lines.append('from __future__ import annotations')
        new_lines.append('')
        new_lines.extend(lines[insert_pos:])

        new_content = '\n'.join(new_lines)

        # 写回文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print(f"✅ 已修改: {file_path}")
        return True

    except Exception as e:
        print(f"❌ 错误 {file_path}: {e}")
        return False


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python fix_annotations.py <目录或文件>")
        print("示例: python fix_annotations.py nanobot/")
        sys.exit(1)

    target = Path(sys.argv[1])

    if not target.exists():
        print(f"错误: 路径不存在: {target}")
        sys.exit(1)

    # 收集需要处理的文件
    files_to_process = []

    if target.is_file():
        if target.suffix == '.py':
            files_to_process.append(target)
    else:
        # 递归查找所有 .py 文件
        files_to_process = list(target.rglob('*.py'))

    if not files_to_process:
        print("没有找到 Python 文件")
        sys.exit(0)

    print(f"找到 {len(files_to_process)} 个 Python 文件")
    print("=" * 60)

    modified_count = 0
    for file_path in files_to_process:
        if add_future_import(file_path):
            modified_count += 1

    print("=" * 60)
    print(f"完成！修改了 {modified_count}/{len(files_to_process)} 个文件")


if __name__ == '__main__':
    main()
