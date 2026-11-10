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

"""Build consumers with CANN dependencies installed under separate prefixes."""

import shutil
import subprocess
from pathlib import Path

import pytest


CMAKE_ROOT = Path(__file__).resolve().parents[3]
PACKAGES = {
    "c_mmpa": ("include/experiment/c_mmpa/mmpa_api.h", None),
    "graph_tuner": (
        "include/experiment/graph_tuner/graph_tuner_errorcode.h",
        "lib64/plugin/opskernel/libgraph_tuner.so",
    ),
    "opcompiler": (
        "include/experiment/opcompiler/tensor_engine/fusion_api.h",
        "lib64/libte_fusion.so",
    ),
    "awatchdog": ("pkg_inc/watchdog/awatchdog.h", "lib64/libascend_watchdog.so"),
    "opat": ("include/experiment/opat/cann_kb_api.h", "lib64/libcann_kb.so"),
}


def run_command(*command: str) -> None:
    """Surface build diagnostics on failure."""
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


def prepare_project(tmp_path: Path, missing: str = "") -> list[str]:
    """Create independent header/library search prefixes for the Find modules."""
    prefixes = []
    for index, (name, (header, library)) in enumerate(PACKAGES.items(), start=1):
        prefix = tmp_path / name
        (prefix / "include").mkdir(parents=True)
        prefixes.append(str(prefix))
        if name != missing:
            path = prefix / header
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"#define HEADER_{name} {index}\n", encoding="utf-8")
        if library:
            path = prefix / library
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
    return [
        "cmake_minimum_required(VERSION 3.16)",
        "project(HeaderCache C)",
        "include(CMakePrintHelpers)",
        f'list(PREPEND CMAKE_MODULE_PATH "{CMAKE_ROOT / "modules"}")',
        f'set(CMAKE_PREFIX_PATH "{";".join(prefixes)}")',
        "set(CMAKE_FIND_USE_CMAKE_SYSTEM_PATH FALSE)",
        "set(CMAKE_FIND_USE_SYSTEM_ENVIRONMENT_PATH FALSE)",
        "set(CMAKE_FIND_USE_CMAKE_ENVIRONMENT_PATH FALSE)",
        "add_library(c_sec_headers INTERFACE)",
    ]


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("existing_cache", [False, True])
def test_separate_header_prefixes(tmp_path: Path, reverse: bool, existing_cache: bool):
    """Each imported header target must expose its own package's include root."""
    if not all(shutil.which(tool) for tool in ("cmake", "cc", "make")):
        pytest.skip("cmake, a C compiler and make are required")
    lines = prepare_project(tmp_path)
    if existing_cache:
        lines.append('set(_INCLUDE_DIR "unrelated-prefix" CACHE PATH "")')
    names = list(PACKAGES)
    if reverse:
        names.reverse()
    lines.extend(f"find_package({name} REQUIRED MODULE)" for name in names)
    headers = []
    for name, (header, _) in PACKAGES.items():
        relative = (
            header.split("/", 2)[-1]
            if header.startswith("include/")
            else header.split("/", 1)[-1]
        )
        headers.append(f"#include <{relative}>")
    headers.append(
        "int main(void) { return "
        + " + ".join(f"HEADER_{name}" for name in PACKAGES)
        + " == 15 ? 0 : 1; }"
    )
    (tmp_path / "main.c").write_text("\n".join(headers) + "\n", encoding="utf-8")
    lines += [
        "add_executable(consumer main.c)",
        "target_link_libraries(consumer PRIVATE "
        + " ".join(f"{name}_headers" for name in PACKAGES)
        + ")",
    ]
    (tmp_path / "CMakeLists.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    build = tmp_path / "build"
    for _ in range(2):
        # Reconfigure the same build tree to exercise persistent find_path caches.
        run_command(
            "cmake", "-S", str(tmp_path), "-B", str(build), "-G", "Unix Makefiles"
        )
        run_command("cmake", "--build", str(build), "--parallel", "2")
        run_command(str(build / "consumer"))


@pytest.mark.parametrize("missing", PACKAGES)
def test_missing_header_after_other_package(tmp_path: Path, missing: str):
    """Another package's successful search must not satisfy a missing header."""
    lines = prepare_project(tmp_path, missing)
    first = "graph_tuner" if missing == "c_mmpa" else "c_mmpa"
    lines += [
        f"find_package({first} REQUIRED MODULE)",
        f"find_package({missing} QUIET MODULE)",
        f"if({missing}_FOUND OR TARGET {missing}_headers)",
        '    message(FATAL_ERROR "Missing header was incorrectly reported as found")',
        "endif()",
    ]
    (tmp_path / "CMakeLists.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    run_command("cmake", "-S", str(tmp_path), "-B", str(tmp_path / "build"))
