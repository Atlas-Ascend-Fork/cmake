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

"""Tests for the image extraction command-line argument validation."""

import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "ci_img_handler.py"


def run_tool(*args):
    """Run the image extraction tool and return the completed process."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def test_rcvr_requires_raw(tmp_path):
    """Reject recovery mode without an output path at argument parsing time."""
    image = tmp_path / "image.bin"
    image.write_bytes(b"raw")

    result = run_tool("-img", str(image), "--rcvr")

    assert result.returncode == 2
    assert "-raw" in result.stderr
    assert "TypeError" not in result.stderr


def test_rcvr_with_raw_succeeds(tmp_path):
    """Preserve the existing recovery behavior when an output path is supplied."""
    image = tmp_path / "image.bin"
    raw = tmp_path / "raw.bin"
    image.write_bytes(b"raw")

    result = run_tool("-img", str(image), "-raw", str(raw), "--rcvr")

    assert result.returncode == 0
    assert raw.read_bytes() == b"raw"


def test_without_rcvr_keeps_existing_error(tmp_path):
    """Keep the existing no-operation error for calls without --rcvr."""
    image = tmp_path / "image.bin"
    image.write_bytes(b"raw")

    result = run_tool("-img", str(image))

    assert result.returncode == 1
    assert "No operation found, do nothing" in result.stderr
