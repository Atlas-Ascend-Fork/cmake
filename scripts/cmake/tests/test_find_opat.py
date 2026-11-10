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

"""Check OPAT package discovery and standard required/optional lookup behavior."""

import subprocess
from pathlib import Path

import pytest


CMAKE_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    "available,mode", [(True, "REQUIRED"), (False, "QUIET"), (False, "REQUIRED")]
)
def test_find_opat(tmp_path: Path, available: bool, mode: str) -> None:
    """The helper uses OPAT's name for result variables and required handling."""
    prefix = tmp_path / "prefix"
    include_dir = prefix / "include"
    library = prefix / "lib64" / "libcann_kb.so"
    if available:
        (include_dir / "experiment" / "opat").mkdir(parents=True)
        (include_dir / "experiment" / "opat" / "cann_kb_api.h").touch()
        library.parent.mkdir()
        library.touch()
        variables = f'set(CMAKE_PREFIX_PATH "{prefix}")\n'
    else:
        # Pin both unavailable results to avoid discovering a host installation.
        variables = (
            'set(_CANN_OPAT_INCLUDE_DIR "" CACHE PATH "" FORCE)\n'
            'set(cann_kb_SHARED_LIBRARY "" CACHE FILEPATH "" FORCE)\n'
        )

    (tmp_path / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.16)\n"
        "project(OpatLookup NONE)\n"
        "include(CMakePrintHelpers)\n"
        f'list(PREPEND CMAKE_MODULE_PATH "{CMAKE_ROOT / "modules"}")\n'
        f"{variables}"
        f"find_package(opat {mode} MODULE)\n"
        f"if(opat_FOUND AND NOT {'TRUE' if available else 'FALSE'})\n"
        '    message(FATAL_ERROR "Unexpected OPAT lookup success")\n'
        f"elseif(NOT opat_FOUND AND {'TRUE' if available else 'FALSE'})\n"
        '    message(FATAL_ERROR "OPAT lookup should succeed")\n'
        "endif()\n"
        "if(opat_FOUND)\n"
        "    if(NOT TARGET cann_kb OR NOT TARGET opat_headers)\n"
        '        message(FATAL_ERROR "OPAT targets are missing")\n'
        "    endif()\n"
        "    get_target_property(location cann_kb IMPORTED_LOCATION)\n"
        f'    if(NOT location STREQUAL "{library}")\n'
        '        message(FATAL_ERROR "Incorrect OPAT library location")\n'
        "    endif()\n"
        "elseif(TARGET cann_kb OR TARGET opat_headers)\n"
        '    message(FATAL_ERROR "Missing OPAT must not create targets")\n'
        "endif()\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        ["cmake", "-S", str(tmp_path), "-B", str(tmp_path / "build")],
        capture_output=True,
        text=True,
        check=False,
    )
    if available or mode == "QUIET":
        assert result.returncode == 0, result.stdout + result.stderr
    else:
        assert result.returncode != 0
        assert "Could NOT find opat" in result.stderr
