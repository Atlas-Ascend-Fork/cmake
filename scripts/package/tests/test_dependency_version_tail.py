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

"""显式依赖组件和短版本前缀的回归。"""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "version" / "check_build_dependencies.py"
SPEC = importlib.util.spec_from_file_location("dependency_tail", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.mark.parametrize(
    "installed,required,expected",
    [
        ("1.2.3", "1.2.3.4", False),
        ("9.2", "9.2.1", False),
        ("9.2", "9.2.0", True),
        ("9.2.1", "9.2", True),
        ("9.2.1.4", "9.2.1", True),
        ("9.2.1", "9.2.2", False),
        ("9.2.1", "9.2.1", True),
        ("9.2", ">=9.2.1", False),
        ("9.2", ">9.2.0", False),
        ("9.2", "<=9.2.0", True),
        ("9.2", "<9.2.1", True),
        ("9.2.1", ">9.2", True),
        ("9.2.1", "<=9.2", False),
    ],
)
def test_explicit_dependency_components(installed, required, expected):
    assert MODULE.check_build_dep_item(installed, required) is expected


@pytest.mark.parametrize(
    "required,warning",
    [
        ("1.2.3.4", True),
        ("1.2.3.0", False),
        ("1.2", False),
        ("1.2.3.4,2.0", True),
        ("1.2.3.4,1.2", False),
        (">=1.2.3,<1.3", False),
    ],
)
def test_real_cli_version_info(tmp_path, required, warning):
    info = tmp_path / "share/info/runtime/version.info"
    info.parent.mkdir(parents=True)
    info.write_text("Version=1.2.3-alpha\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path), "runtime", required],
        capture_output=True,
        text=True,
        check=False,
    )
    # 依赖不满足仍沿用警告，不修改 CLI 退出码契约。
    assert result.returncode == 0
    assert ("Check build dependency failed" in result.stderr) is warning
