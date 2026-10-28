#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# -----------------------------------------------------------------------------------------------------------
# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.
# -----------------------------------------------------------------------------------------------------------

"""iwyu_log_parser 失败状态传播测试。"""

import logging
import sys
from pathlib import Path

import iwyu_log_parser
import pytest
from iwyu_log_parser import IWYU_FIX_MARKER
from pytest import LogCaptureFixture


def _make_remove_log(file_path: Path) -> str:
    return (
        f"{file_path} should remove these lines:\n"
        '- #include "redundant.h"  // lines 1-1\n'
    )


def test_report_out_failure_exits(tmp_path: Path, caplog: LogCaptureFixture) -> None:
    log_file = tmp_path / "test.log"
    log_file.write_text("", encoding="utf-8")
    report_file = tmp_path / "missing" / "report.txt"
    sys.argv = ["prog", str(log_file), "--report-out", str(report_file)]

    with pytest.raises(SystemExit, match="1"):
        iwyu_log_parser.main()

    assert "保存报告失败" in caplog.text
    assert not report_file.exists()


def test_fix_failure_exits_after_processing_other_files(
    tmp_path: Path, caplog: LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    good_file = tmp_path / "good.cpp"
    good_file.write_text('#include "redundant.h"\n', encoding="utf-8")
    bad_file = tmp_path / "bad.cpp"
    bad_file.mkdir()
    log_file = tmp_path / "test.log"
    log_file.write_text(
        _make_remove_log(good_file) + _make_remove_log(bad_file),
        encoding="utf-8",
    )
    sys.argv = ["prog", str(log_file), "--fix"]

    with pytest.raises(SystemExit, match="1"):
        iwyu_log_parser.main()

    assert "以下文件处理失败" in caplog.text
    assert str(bad_file) in caplog.text
    assert IWYU_FIX_MARKER in good_file.read_text(encoding="utf-8")
    assert "无需要注释的自定义冗余头文件" not in caplog.text
