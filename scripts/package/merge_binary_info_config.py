#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# -----------------------------------------------------------------------------------------------------------
# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.
# -----------------------------------------------------------------------------------------------------------

"""合并算子binary_info_config.json。"""

import argparse
import json
from pathlib import Path
import sys
from typing import List


def load_json_file(json_file: str):
    """读取单份配置，交由合并逻辑处理算子字段。"""
    return json.loads(Path(json_file).read_text(encoding="utf-8"))


def save_json_file(output_file: str, content):
    """写入结果，支持当前目录文件和多层输出目录。"""
    destination = Path(output_file)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(content, ensure_ascii=True, indent=2), encoding="utf-8"
    )


def update_config(base_content, update_content):
    """按输入顺序合并算子；普通字段取update，binaryList保持拼接语义。"""
    result = {}
    for operator in dict.fromkeys((*base_content, *update_content)):
        previous = base_content.get(operator, {})
        incoming = update_content.get(operator, {})
        if isinstance(previous, dict) and isinstance(incoming, dict):
            result[operator] = _merge_operator_config(previous, incoming)
        else:
            result[operator] = update_content.get(operator, base_content.get(operator))
    return result


def _merge_operator_config(base_op, update_op):
    """字典合并保留首见字段顺序，binaryList单独处理。"""
    merged = {**base_op, **update_op}
    if "binaryList" in merged:
        merged["binaryList"] = _merge_binary_list(base_op, update_op)
    return merged


def _merge_binary_list(base_op, update_op):
    """非列表值沿用空列表约定，返回不共享输入列表的新结果。"""
    sequences = (base_op.get("binaryList"), update_op.get("binaryList"))
    return [
        item
        for sequence in sequences
        if isinstance(sequence, list)
        for item in sequence
    ]


def merge_files(files: List[str], priority: str = "last"):
    """顺序读取配置，first反转每次覆盖的方向。"""
    if not files:
        return {}
    first, *remaining = files
    merged = load_json_file(first)
    for filename in remaining:
        incoming = load_json_file(filename)
        pair = (incoming, merged) if priority == "first" else (merged, incoming)
        merged = update_config(*pair)
    return merged


def parse_args(argv: List[str]):
    """解析双文件/批量模式，并在读写文件前检查成对参数。"""
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_argument_group("Input binary config files")
    for role in ("base", "update"):
        inputs.add_argument(
            f"--{role}-file", help=f"the {role} binary_info_config file"
        )
    inputs.add_argument("--input-files", nargs="+", help="batch merge multiple files")
    parser.add_argument(
        "--output-file",
        required=True,
        type=lambda path: str(Path(path).resolve()),
        help="the output binary_info_config file",
    )
    parser.add_argument(
        "--priority", choices=["first", "last"], default="last", help="merge priority"
    )
    args = parser.parse_args(argv)
    if not args.input_files and (not args.base_file or not args.update_file):
        parser.error("provide --input-files or both --base-file and --update-file")
    return args


def main(argv: List[str]) -> bool:
    """两种输入模式共享同一优先级处理路径。"""
    args = parse_args(argv)
    sources = args.input_files or [args.base_file, args.update_file]
    save_json_file(args.output_file, merge_files(sources, args.priority))
    return True


if __name__ == "__main__":
    if not main(sys.argv[1:]):  # pragma: no cover
        sys.exit(1)  # pragma: no cover
