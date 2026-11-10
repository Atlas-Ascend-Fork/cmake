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

"""Link and run consumers of each individual GTest imported target offline."""

import shutil
import subprocess
from pathlib import Path

import pytest


CMAKE_ROOT = Path(__file__).resolve().parents[3]
LIBRARIES = ("gtest", "gtest_main", "gmock", "gmock_main")


def run_command(*command: str) -> None:
    """Show configure, linker and runtime diagnostics on failure."""
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


def build_library_cache(root: Path, shared: bool) -> None:
    """Build four real libraries with GoogleTest's dependency relationships."""
    source = root / "libraries"
    source.mkdir()
    header = source / "gtest" / "gtest.h"
    header.parent.mkdir()
    header.write_text("int gtest_probe();\nint gmock_probe();\n", encoding="utf-8")
    (source / "gtest.cpp").write_text(
        "int gtest_probe() { return 21; }\n", encoding="utf-8"
    )
    (source / "gmock.cpp").write_text(
        '#include "gtest/gtest.h"\nint gmock_probe() { return 2 * gtest_probe(); }\n',
        encoding="utf-8",
    )
    for name in ("gtest", "gmock"):
        expected = 21 if name == "gtest" else 42
        (source / f"{name}_main.cpp").write_text(
            '#include "gtest/gtest.h"\nint test_body();\n'
            f"int main() {{ return test_body() || {name}_probe() != {expected}; }}\n",
            encoding="utf-8",
        )
    (source / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.16)\n"
        "project(GTestFixture CXX)\n"
        'set(CMAKE_INSTALL_RPATH "$ORIGIN")\n'
        "foreach(name gtest gtest_main gmock gmock_main)\n"
        "    add_library(${name} ${name}.cpp)\n"
        "    set_target_properties(${name} PROPERTIES VERSION 1.14.0)\n"
        "endforeach()\n"
        "target_link_libraries(gtest_main PUBLIC gtest)\n"
        "target_link_libraries(gmock PUBLIC gtest)\n"
        "target_link_libraries(gmock_main PUBLIC gmock)\n"
        "install(TARGETS gtest gtest_main gmock gmock_main\n"
        "    ARCHIVE DESTINATION lib LIBRARY DESTINATION lib64)\n"
        "install(FILES gtest/gtest.h DESTINATION include/gtest)\n",
        encoding="utf-8",
    )
    build = root / "libraries-build"
    package = "gtest_shared" if shared else "gtest"
    cache = root / "cache" / "lib_cache" / package
    run_command(
        "cmake",
        "-S",
        str(source),
        "-B",
        str(build),
        "-G",
        "Unix Makefiles",
        f"-DCMAKE_INSTALL_PREFIX={cache}",
        f"-DBUILD_SHARED_LIBS={'ON' if shared else 'OFF'}",
    )
    run_command(
        "cmake", "--build", str(build), "--target", "install", "--parallel", "2"
    )


@pytest.mark.parametrize("shared", [False, True], ids=["static", "shared"])
@pytest.mark.parametrize("target", LIBRARIES)
def test_individual_target_links(tmp_path: Path, shared: bool, target: str) -> None:
    """Consumers linking one public target inherit every required library."""
    if not all(shutil.which(tool) for tool in ("cmake", "c++", "make")):
        pytest.skip("cmake, a C++ compiler and make are required")
    build_library_cache(tmp_path, shared)
    namespace = "GTestShared" if shared else "GTest"
    module = "gtest_shared.cmake" if shared else "gtest.cmake"
    probe = "gmock" if target.startswith("gmock") else "gtest"
    expected = 42 if probe == "gmock" else 21
    entry = "test_body" if target.endswith("_main") else "main"
    condition = f"{probe}_probe() != {expected}"
    if probe == "gmock":
        condition += " || gtest_probe() != 21"
    (tmp_path / "main.cpp").write_text(
        f"#include <gtest/gtest.h>\nint {entry}() {{ return {condition}; }}\n",
        encoding="utf-8",
    )
    (tmp_path / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.16)\n"
        "project(GTestConsumer CXX)\n"
        'set(CANN_3RD_LIB_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cache")\n'
        f'include("{CMAKE_ROOT / "third_party" / module}")\n'
        "add_executable(consumer main.cpp)\n"
        f"target_link_libraries(consumer PRIVATE {namespace}::{target})\n",
        encoding="utf-8",
    )
    build = tmp_path / "consumer-build"
    run_command("cmake", "-S", str(tmp_path), "-B", str(build), "-G", "Unix Makefiles")
    run_command("cmake", "--build", str(build), "--parallel", "2")
    run_command(str(build / "consumer"))
