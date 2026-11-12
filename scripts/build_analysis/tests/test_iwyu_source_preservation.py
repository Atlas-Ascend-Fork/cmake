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

"""IWYU 源码改写保留编码字节与换行符的命令行回归测试。"""

import subprocess
import sys
from pathlib import Path

import iwyu_log_parser
import pytest


@pytest.mark.parametrize("option", ["--fix", "--clean-commented"])
@pytest.mark.parametrize(
    ("line_ending", "body"),
    [
        pytest.param(
            b"\n", 'const char *name = "算子"; // 中文注释\n'.encode(), id="utf8-lf"
        ),
        pytest.param(
            b"\r\n",
            'const char *name = "算子"; // 中文注释\r\n'.encode(),
            id="utf8-crlf",
        ),
        pytest.param(
            b"\n",
            'const char *name = "算子"; // 中文注释\n'.encode("gb18030"),
            id="gb18030-lf",
        ),
        pytest.param(
            b"\r\n",
            'const char *name = "算子"; // 中文注释\r\n'.encode("gb18030"),
            id="gb18030-crlf",
        ),
        pytest.param(b"\n", b'const char *name = "caf\xe9";\n', id="latin1-lf"),
        pytest.param(b"", b"", id="include-without-final-newline"),
    ],
)
def test_cli_preserves_source_bytes(
    tmp_path: Path, option: str, line_ending: bytes, body: bytes
) -> None:
    source = tmp_path / "sample.cpp"
    include = b'#include "unused.h"'
    marked_include = b"// [iwyu-fix] " + include
    source_include = include if option == "--fix" else marked_include
    source.write_bytes(source_include + line_ending + body)
    log_file = tmp_path / "iwyu.log"
    log_file.write_text(
        f'{source} should remove these lines:\n- #include "unused.h"  // lines 1-1\n',
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, iwyu_log_parser.__file__, str(log_file), option],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    expected = marked_include + line_ending + body if option == "--fix" else body
    assert source.read_bytes() == expected
