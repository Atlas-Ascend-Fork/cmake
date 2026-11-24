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

"""Build consumers of generated rdma-core headers using an offline source cache."""

import shutil
import subprocess
from pathlib import Path

import pytest


CMAKE_ROOT = Path(__file__).resolve().parents[3]


def run_command(*command: str) -> None:
    """Expose configure and build diagnostics when a command fails."""
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("generator", ["Ninja", "Unix Makefiles"])
def test_rdma_core_headers_build(
    tmp_path: Path, generator: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The kern-abi build must finish before a consumer compiles its includes."""
    backend = "ninja" if generator == "Ninja" else "make"
    if not all(
        shutil.which(tool) for tool in ("cmake", "cc", "pkg-config", "make", backend)
    ):
        pytest.skip(f"cmake, a C compiler, pkg-config, make and {backend} are required")
    monkeypatch.delenv("CMAKE_BUILD_PARALLEL_LEVEL", raising=False)
    monkeypatch.setenv(
        "CMAKE_GENERATOR",
        "Ninja" if generator == "Unix Makefiles" else "Unix Makefiles",
    )

    source = tmp_path / "cache" / "rdma-core"
    source.mkdir(parents=True)
    (source / "rdma-core-42.7.patch").write_text("", encoding="utf-8")
    (source / "rdma_user_cm.h").write_text("#define RDMA_PROBE 42\n", encoding="utf-8")
    (source / "record_makeflags.cmake").write_text(
        f'file(WRITE "{tmp_path / "build-makeflags.txt"}" "$ENV{{MAKEFLAGS}}")\n',
        encoding="utf-8",
    )
    (source / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.16)\n"
        "project(RdmaFixture NONE)\n"
        'set(header "${CMAKE_CURRENT_BINARY_DIR}/include/rdma/rdma_user_cm.h")\n'
        'add_custom_command(OUTPUT "${header}"\n'
        "    COMMAND ${CMAKE_COMMAND} -P ${CMAKE_CURRENT_SOURCE_DIR}/record_makeflags.cmake\n"
        '    COMMAND ${CMAKE_COMMAND} -E make_directory "${CMAKE_CURRENT_BINARY_DIR}/include/rdma"\n'
        '    COMMAND ${CMAKE_COMMAND} -E copy "${CMAKE_CURRENT_SOURCE_DIR}/rdma_user_cm.h" "${header}"\n'
        '    DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/rdma_user_cm.h" VERBATIM)\n'
        'add_custom_target(kern-abi DEPENDS "${header}")\n',
        encoding="utf-8",
    )
    (tmp_path / "main.c").write_text(
        "#include <rdma/rdma_user_cm.h>\n"
        "int main(void) { return RDMA_PROBE == 42 ? 0 : 1; }\n",
        encoding="utf-8",
    )
    (tmp_path / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.16)\n"
        "project(RdmaConsumer C)\n"
        "set(ENABLE_UNIFIED_BUILD TRUE)\n"
        f'include("{CMAKE_ROOT / "function" / "prepare.cmake"}")\n'
        'set(CANN_3RD_LIB_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cache")\n'
        f'include("{CMAKE_ROOT / "third_party" / "rdma-core.cmake"}")\n'
        "add_executable(consumer main.c)\n"
        "target_link_libraries(consumer PRIVATE rdma_core_headers)\n",
        encoding="utf-8",
    )
    build = tmp_path / "build"
    run_command("cmake", "-S", str(tmp_path), "-B", str(build), "-G", generator)
    run_command("cmake", "--build", str(build), "--parallel", "16")
    run_command(str(build / "consumer"))
    if generator == "Unix Makefiles":
        flags = (tmp_path / "build-makeflags.txt").read_text(encoding="utf-8")
        assert "-j16" in flags.split(), flags
        assert "--jobserver-" in flags, flags

    # A fresh consumer build can reuse the generated header cache.
    cached_build = tmp_path / "cached-build"
    run_command("cmake", "-S", str(tmp_path), "-B", str(cached_build), "-G", generator)
    run_command("cmake", "--build", str(cached_build), "--parallel", "2")
    run_command(str(cached_build / "consumer"))
