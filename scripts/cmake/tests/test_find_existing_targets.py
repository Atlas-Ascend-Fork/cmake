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

"""Exercise Find modules with dependency targets supplied by a parent project."""

import subprocess
from pathlib import Path

import pytest


CMAKE_ROOT = Path(__file__).resolve().parents[3]
PACKAGES = {
    "adump": "adump_server adump_headers adcore ascend_dump",
    "ascend_hal": "ascend_hal ascend_hal_stub ascend_hal_headers",
    "atrace": "atrace_share atrace_headers",
    "awatchdog": "awatchdog_share awatchdog_headers",
    "c_base": "c_base_static c_json_static",
    "datagw": "dgw_client datagw_headers",
    "error_manager": "error_manager stub_error_manager error_manager_headers",
    "graph_tuner": "graph_tuner graph_tuner_headers",
    "hcomm": "hcomm hcomm_headers",
    "metadef": (
        "exe_graph metadef opp_registry rt2_registry_static "
        "metadef_headers exe_graph_headers"
    ),
    "mmpa": "mmpa static_mmpa mmpa_headers",
    "msprof": (
        "msprofiler_fwk_share msprofiler profapi profapi_share profimpl msprof_headers"
    ),
    "opat": "cann_kb opat_headers",
    "opcompiler": "te_fusion opcompiler_headers",
    "platform": "platform platform_headers",
    "runtime": "runtime runtime_headers",
    "slog": "slog alog",
    "unified_dlog": "unified_dlog slog_headers unified_dlog_headers",
}

SCOPED_PACKAGES = {
    "ascend_hal": ("pkg_inc/driver/ascend_hal.h", "devlib/libascend_hal.so"),
    "atrace": ("pkg_inc/trace/atrace_pub.h", "lib64/libascend_trace.so"),
    "error_manager": (
        "include/base/err_msg.h",
        "pkg_inc/base/err_mgr.h",
        "lib64/liberror_manager.so",
        "devlib/linux/x86_64/liberror_manager.so",
    ),
    "hcomm": (
        "include/hccl/hccl_comm.h",
        "pkg_inc/hccl/base.h",
        "lib64/libhcomm.so",
    ),
    "msprof": (
        "pkg_inc/profiling/aprof_pub.h",
        "lib64/libmsprofiler.so",
        "lib64/libprofapi.so",
        "lib64/libprofimpl.so",
    ),
}


def configure(source: Path) -> subprocess.CompletedProcess:
    """Configure a real project without requiring an installed CANN toolkit."""
    return subprocess.run(
        ["cmake", "-S", str(source), "-B", str(source / "build")],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize("package", PACKAGES)
@pytest.mark.parametrize("target_kind", ["INTERFACE", "INTERFACE IMPORTED"])
def test_reuse_parent_targets(tmp_path: Path, package: str, target_kind: str):
    """Sibling consumers reuse complete targets and report a successful lookup."""
    targets = PACKAGES[package].split()
    definitions = "\n".join(
        f"add_library({target} {target_kind})\n"
        f"target_compile_definitions({target} INTERFACE FROM_PARENT=1)"
        for target in targets
    )
    (tmp_path / "CMakeLists.txt").write_text(
        f"""cmake_minimum_required(VERSION 3.16)
project(ExistingTargets NONE)
list(PREPEND CMAKE_MODULE_PATH "{CMAKE_ROOT / "modules"}")
{definitions}
add_subdirectory(first)
add_subdirectory(second)
""",
        encoding="utf-8",
    )
    for child in ["first", "second"]:
        consumer = tmp_path / child
        consumer.mkdir()
        (consumer / "CMakeLists.txt").write_text(
            f"""cmake_policy(PUSH)
find_package({package} REQUIRED MODULE)
if(NOT {package}_FOUND)
    message(FATAL_ERROR "Existing targets must satisfy {package}")
endif()
find_package({package} REQUIRED MODULE)
foreach(target IN ITEMS {PACKAGES[package]})
    get_target_property(definitions ${{target}} INTERFACE_COMPILE_DEFINITIONS)
    if(NOT definitions STREQUAL "FROM_PARENT=1")
        message(FATAL_ERROR "Target properties changed: ${{target}}")
    endif()
endforeach()
cmake_policy(POP)
""",
            encoding="utf-8",
        )
    result = configure(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("package", PACKAGES)
def test_incomplete_targets_report_missing_dependencies(tmp_path: Path, package: str):
    """A partial target set retains the existing actionable failure diagnostic."""
    targets = PACKAGES[package].split()
    (tmp_path / "CMakeLists.txt").write_text(
        f"""cmake_minimum_required(VERSION 3.16)
project(IncompleteTargets NONE)
list(PREPEND CMAKE_MODULE_PATH "{CMAKE_ROOT / "modules"}")
add_library({targets[0]} INTERFACE)
find_package({package} REQUIRED MODULE)
""",
        encoding="utf-8",
    )
    result = configure(tmp_path)
    assert result.returncode != 0
    assert "Some (but not all) targets" in result.stderr
    assert f"Targets Defined: {targets[0]}" in result.stderr
    assert "Targets not yet defined:" in result.stderr
    for target in targets[1:]:
        assert target in result.stderr


@pytest.mark.parametrize("package", SCOPED_PACKAGES)
def test_reuse_targets_after_function_lookup(tmp_path: Path, package: str):
    """A helper's FOUND variable expires while its imported targets stay visible."""
    prefix = tmp_path / "prefix"
    for relative in SCOPED_PACKAGES[package]:
        path = prefix / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    (tmp_path / "CMakeLists.txt").write_text(
        f"""cmake_minimum_required(VERSION 3.16)
project(ScopedLookup NONE)
include(CMakePrintHelpers)
list(PREPEND CMAKE_MODULE_PATH "{CMAKE_ROOT / "modules"}")
set(CMAKE_PREFIX_PATH "{prefix}")
set(ASCEND_INSTALL_PATH "{prefix}")
set(CMAKE_SYSTEM_PROCESSOR x86_64)
function(load_dependency)
    find_package({package} REQUIRED MODULE)
endfunction()
load_dependency()
find_package({package} REQUIRED MODULE)
if(NOT {package}_FOUND)
    message(FATAL_ERROR "Existing targets must satisfy {package}")
endif()
foreach(target IN ITEMS {PACKAGES[package]})
    if(NOT TARGET ${{target}})
        message(FATAL_ERROR "Dependency target missing: ${{target}}")
    endif()
endforeach()
""",
        encoding="utf-8",
    )
    result = configure(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    "package,missing",
    [(name, target) for name in SCOPED_PACKAGES for target in PACKAGES[name].split()],
)
def test_missing_exported_target(tmp_path: Path, package: str, missing: str):
    """Each library and header target belongs to the package completeness check."""
    definitions = "\n".join(
        f"add_library({target} INTERFACE)"
        for target in PACKAGES[package].split()
        if target != missing
    )
    (tmp_path / "CMakeLists.txt").write_text(
        f"""cmake_minimum_required(VERSION 3.16)
project(MissingExport NONE)
list(PREPEND CMAKE_MODULE_PATH "{CMAKE_ROOT / "modules"}")
{definitions}
find_package({package} REQUIRED MODULE)
""",
        encoding="utf-8",
    )
    result = configure(tmp_path)
    assert result.returncode != 0
    assert "Some (but not all) targets" in result.stderr
    assert f"Targets not yet defined: {missing}" in result.stderr
