# -----------------------------------------------------------------------------------------------------------
# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.
# -----------------------------------------------------------------------------------------------------------

"""GTest shared 缓存的真实 CMake 配置、链接和重建分支回归。"""

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LIBRARIES = ("gtest", "gmock", "gtest_main", "gmock_main")


def run_command(*command):
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    return result


def create_cache(root, libdir, versioned):
    compiler = shutil.which("cc")
    if compiler is None:
        pytest.skip("C compiler is required for shared library fixtures")
    cache = root / "third_party" / "lib_cache" / "gtest_shared"
    include = cache / "include" / "gtest"
    include.mkdir(parents=True)
    (include / "gtest.h").write_text(
        "\n".join(f"int {name}_value(void);" for name in LIBRARIES) + "\n"
    )
    library_dir = cache / libdir
    library_dir.mkdir()
    for index, name in enumerate(LIBRARIES, start=1):
        source = root / f"{name}.c"
        source.write_text(f"int {name}_value(void) {{ return {index}; }}\n")
        library = library_dir / f"lib{name}.so"
        output = library.with_name(library.name + ".1.14.0") if versioned else library
        run_command(compiler, "-shared", "-fPIC", str(source), "-o", str(output))
        if versioned:
            library.symlink_to(output.name)
    return cache


def configure_consumer(root, force=False):
    cmake = shutil.which("cmake")
    if cmake is None:
        pytest.skip("CMake is required")
    source = root / "project"
    source.mkdir()
    (source / "consumer.c").write_text(
        "#include <gtest/gtest.h>\nint main(void) { return "
        + " + ".join(f"{name}_value()" for name in LIBRARIES)
        + " != 10; }\n"
    )
    (source / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.16)\n"
        "project(shared_cache C)\n"
        f'set(CANN_3RD_LIB_PATH "{root.as_posix()}/third_party")\n'
        'set(CANN_CXX11_ABI "0")\n'
        f"set(FORCE_REBUILD_CANN_3RD {'ON' if force else 'OFF'})\n"
        f'include("{REPO_ROOT.as_posix()}/third_party/gtest_shared.cmake")\n'
        "add_executable(consumer consumer.c)\n"
        "target_link_libraries(consumer PRIVATE "
        + " ".join(f"GTestShared::{name}" for name in LIBRARIES)
        + ")\n"
        'file(WRITE "${CMAKE_BINARY_DIR}/locations.txt" "")\n'
        "foreach(name gtest gmock gtest_main gmock_main)\n"
        "  get_target_property(location GTestShared::${name} IMPORTED_LOCATION)\n"
        '  file(APPEND "${CMAKE_BINARY_DIR}/locations.txt" "${location}\\n")\n'
        "endforeach()\n"
    )
    build = root / "build"
    run_command(cmake, "-S", str(source), "-B", str(build))
    return cmake, build


@pytest.mark.parametrize("libdir", ["lib", "lib64"])
@pytest.mark.parametrize("versioned", [False, True])
def test_cached_shared_libraries_link_and_run(tmp_path, libdir, versioned):
    cache = create_cache(tmp_path, libdir, versioned)
    cmake, build = configure_consumer(tmp_path)
    assert (build / "locations.txt").read_text().splitlines() == [
        str(cache / libdir / f"lib{name}.so") for name in LIBRARIES
    ]
    run_command(cmake, "--build", str(build), "--parallel", "2")
    run_command(str(build / "consumer"))


@pytest.mark.parametrize("force", [False, True])
def test_build_branch_uses_external_project_install_locations(tmp_path, force):
    if force:
        create_cache(tmp_path, "lib", versioned=False)
    _, build = configure_consumer(tmp_path, force)
    cache = tmp_path / "third_party" / "lib_cache" / "gtest_shared"
    assert (build / "locations.txt").read_text().splitlines() == [
        str(cache / "lib64" / f"lib{name}.so.1.14.0") for name in LIBRARIES
    ]
    assert (build / "gtest_shared_build-prefix").is_dir()
