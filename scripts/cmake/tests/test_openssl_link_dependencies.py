# -----------------------------------------------------------------------------------------------------------
# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.
# -----------------------------------------------------------------------------------------------------------

"""OpenSSL 静态导入目标的传递链接依赖回归。"""

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def run_command(*command):
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    ("target", "function"),
    [
        ("OpenSSL::SSL", "ssl_value"),
        ("ssl_static", "ssl_value"),
        ("OpenSSL::Crypto", "crypto_value"),
    ],
)
def test_imported_target_links_transitive_library(tmp_path, target, function):
    cmake, compiler, archiver = (shutil.which(name) for name in ("cmake", "cc", "ar"))
    if not all((cmake, compiler, archiver)):
        pytest.skip("CMake, a C compiler and ar are required")

    cache = tmp_path / "third_party" / "lib_cache" / "openssl"
    headers = cache / "include" / "openssl"
    headers.mkdir(parents=True)
    (headers / "ssl.h").write_text("int ssl_value(void);\nint crypto_value(void);\n")
    libraries = cache / "lib"
    libraries.mkdir()
    for name, source in {
        "crypto": "int crypto_value(void) { return 42; }\n",
        "ssl": "int crypto_value(void);\nint ssl_value(void) { return crypto_value(); }\n",
    }.items():
        source_file = tmp_path / f"{name}.c"
        object_file = tmp_path / f"{name}.o"
        source_file.write_text(source)
        run_command(compiler, "-c", str(source_file), "-o", str(object_file))
        run_command(archiver, "rcs", str(libraries / f"lib{name}.a"), str(object_file))

    (tmp_path / "main.c").write_text(
        f"#include <openssl/ssl.h>\nint main(void) {{ return {function}() != 42; }}\n"
    )
    (tmp_path / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.16)\n"
        "project(openssl_links C)\n"
        'set(CANN_3RD_LIB_PATH "${CMAKE_CURRENT_SOURCE_DIR}/third_party")\n'
        f'include("{REPO_ROOT.as_posix()}/third_party/openssl.cmake")\n'
        "add_executable(consumer main.c)\n"
        f"target_link_libraries(consumer PRIVATE {target})\n"
    )
    build = tmp_path / "build"
    run_command(cmake, "-S", str(tmp_path), "-B", str(build))
    run_command(cmake, "--build", str(build))
    run_command(str(build / "consumer"))
