# -----------------------------------------------------------------------------------------------------------
# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.
# -----------------------------------------------------------------------------------------------------------

"""真实查找模块应允许消费者重复请求依赖，不需要编译器或真实共享库。"""

import shutil
import subprocess
from pathlib import Path

import pytest

CMAKE_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module", name="cmake_tools")
def _cmake_tools():
    executable = shutil.which("cmake")
    if not executable:
        pytest.skip("CMake is required")
    ninja = shutil.which("ninja")
    if ninja:
        return executable, "Ninja", ninja
    make = shutil.which("make")
    if make:
        return executable, "Unix Makefiles", make
    return pytest.skip("Ninja or make is required")


@pytest.mark.parametrize(
    "case",
    [
        "single",
        "same_scope",
        "two_functions",
        "parent_child",
        "siblings",
        "quiet_missing",
        "required_missing",
    ],
)
def test_find_aihac_codegen(tmp_path, cmake_tools, case):
    cmake_executable, generator, make_program = cmake_tools
    source = tmp_path / "source"
    source.mkdir()
    prefix = tmp_path / "prefix"
    library = prefix / "lib64" / "libaihac_codegen.so"
    library.parent.mkdir(parents=True)
    if case not in ("quiet_missing", "required_missing"):
        # 仅验证真实 find_library 和 configure/目标属性，不编译或链接占位文件。
        library.write_bytes(b"configure-only placeholder\n")

    check_found = (
        "find_cann_package(aihac_codegen REQUIRED)\n"
        "if(NOT aihac_codegen_FOUND OR NOT TARGET aihac_codegen)\n"
        '  message(FATAL_ERROR "aihac_codegen must be found with an imported target")\n'
        "endif()\n"
        "get_target_property(found_location aihac_codegen IMPORTED_LOCATION)\n"
        f'if(NOT "${{found_location}}" STREQUAL "{library.as_posix()}")\n'
        '  message(FATAL_ERROR "Wrong library selected: ${found_location}")\n'
        "endif()\n"
    )
    if case == "single":
        body = check_found
    elif case == "same_scope":
        body = check_found + check_found
    elif case == "two_functions":
        body = (
            "function(consumer_one)\n" + check_found + "endfunction()\n"
            "function(consumer_two)\n" + check_found + "endfunction()\n"
            "consumer_one()\nconsumer_two()\n"
        )
    elif case == "parent_child":
        child = source / "child"
        child.mkdir()
        (child / "CMakeLists.txt").write_text(
            check_found
            + "get_target_property(marker aihac_codegen CANN_TEST_MARKER)\n"
            + 'if(NOT "${marker}" STREQUAL "parent-target")\n'
            + '  message(FATAL_ERROR "Existing parent target must be preserved")\n'
            + "endif()\n",
            encoding="utf-8",
        )
        body = (
            check_found
            + 'set_property(TARGET aihac_codegen PROPERTY CANN_TEST_MARKER "parent-target")\n'
            + "add_subdirectory(child)\n"
        )
    elif case == "siblings":
        for name in ("one", "two"):
            child = source / name
            child.mkdir()
            (child / "CMakeLists.txt").write_text(check_found, encoding="utf-8")
        body = "add_subdirectory(one)\nadd_subdirectory(two)\n"
    elif case == "quiet_missing":
        body = (
            "find_cann_package(aihac_codegen QUIET)\n"
            "if(aihac_codegen_FOUND OR TARGET aihac_codegen)\n"
            '  message(FATAL_ERROR "Missing package must not report success or create a target")\n'
            "endif()\n"
        )
    else:
        body = "find_cann_package(aihac_codegen REQUIRED)\n"

    (source / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.16)\n"
        "set(CMAKE_SYSTEM_NAME Linux)\n"
        "project(AihacFindRegression NONE)\n"
        f'include("{CMAKE_ROOT.as_posix()}/function/prepare.cmake")\n'
        "set(TOPLEVEL_PROJECT ON)\n"
        f'list(PREPEND CMAKE_MODULE_PATH "{CMAKE_ROOT.as_posix()}/modules")\n'
        f'set(CMAKE_PREFIX_PATH "{prefix.as_posix()}")\n'
        # 禁止宿主的环境变量或系统安装让 missing 场景意外命中。
        "set(CMAKE_FIND_USE_CMAKE_ENVIRONMENT_PATH FALSE)\n"
        "set(CMAKE_FIND_USE_SYSTEM_ENVIRONMENT_PATH FALSE)\n"
        "set(CMAKE_FIND_USE_PACKAGE_ROOT_PATH FALSE)\n"
        "set(CMAKE_FIND_USE_CMAKE_SYSTEM_PATH FALSE)\n" + body,
        encoding="utf-8",
    )
    # 使用实际 Ninja 或 make 完成生成阶段，不编译或链接占位文件。
    result = subprocess.run(
        [
            cmake_executable,
            "-S",
            str(source),
            "-B",
            str(tmp_path / "build"),
            "-G",
            generator,
            f"-DCMAKE_MAKE_PROGRAM={make_program}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if case == "required_missing":
        assert result.returncode != 0
        assert "Could NOT find aihac_codegen" in result.stdout + result.stderr
    else:
        assert result.returncode == 0, result.stdout + result.stderr
