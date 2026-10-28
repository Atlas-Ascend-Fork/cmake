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

"""Tests for the package cleanup script."""

import os
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("directory_name", ["plain", "with space", "with\nnewline"])
def test_cleanup_passes_current_directory_as_one_argument(tmp_path, directory_name):
    """目录名包含 shell 分隔符时也应将当前目录作为单个参数传给 rm。"""
    cleanup_script = Path(__file__).parents[2] / "install" / "cleanup.sh"
    working_directory = tmp_path / directory_name
    working_directory.mkdir()

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_rm = fake_bin / "rm"
    fake_rm.write_text("#!/bin/sh\nprintf '%s\\0' \"$@\"\n", encoding="utf-8")
    fake_rm.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
    result = subprocess.run(
        ["/bin/sh", str(cleanup_script)],
        cwd=working_directory,
        env=env,
        capture_output=True,
        check=True,
    )

    assert result.stdout.split(b"\0") == [
        b"-rf",
        b"--",
        os.fsencode(working_directory),
        b"",
    ]
