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

"""Build CSEC consumers using an offline native Makefile source fixture."""

import hashlib
import os
import re
import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest


CMAKE_ROOT = Path(__file__).resolve().parents[3]


def run_command(*command: str, library_dir: Path | None = None) -> str:
    """Include build diagnostics when a command fails."""
    environment = os.environ.copy()
    if library_dir is not None:
        # Prefer the fixture library over CSEC supplied by the CI environment.
        search_path = environment.get("LD_LIBRARY_PATH", "")
        environment["LD_LIBRARY_PATH"] = os.pathsep.join(
            path for path in (str(library_dir), search_path) if path
        )
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
        env=environment,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    return output


def prepare_source(tmp_path: Path) -> Path:
    """Package the upstream Makefile layout for the real patch/build/install flow."""
    source = tmp_path / "dependency"
    (source / "include").mkdir(parents=True)
    (source / "include" / "securec.h").write_text(
        "int csec_probe(void);\n", encoding="utf-8"
    )
    (source / "probe.c").write_text(
        "int csec_probe(void) { return 42; }\n", encoding="utf-8"
    )
    (source / "Makefile").write_text(
        "PROJECT = libboundscheck.so\n"
        "CC ?= cc\n"
        "OBJECTS = probe.o\n"
        "$(PROJECT): $(OBJECTS)\n"
        "\tmkdir -p lib\n"
        "\t$(CC) -shared -o lib/$@ obj/probe.o\n"
        "probe.o: probe.c\n"
        "\tmkdir -p obj\n"
        "\t$(CC) -fPIC -c probe.c -o obj/probe.o\n",
        encoding="utf-8",
    )
    cache = tmp_path / "cache"
    cache.mkdir()
    archive = cache / "libboundscheck-v1.1.16.tar.gz"
    with tarfile.open(archive, "w:gz") as package:
        package.add(source, arcname="libboundscheck-v1.1.16")

    # Substitute only the digest for this locally generated source archive.
    module = (CMAKE_ROOT / "third_party" / "csec.cmake").read_text(encoding="utf-8")
    module = re.sub(
        r"URL_HASH SHA256=[0-9a-f]+",
        "URL_HASH SHA256=" + hashlib.sha256(archive.read_bytes()).hexdigest(),
        module,
    )
    (tmp_path / "csec.cmake").write_text(module, encoding="utf-8")
    shutil.copyfile(
        CMAKE_ROOT / "third_party" / "csec_patch.cmake", tmp_path / "csec_patch.cmake"
    )
    return archive


@pytest.mark.parametrize("generator", ["Ninja", "Unix Makefiles"])
def test_csec_consumer_build(tmp_path: Path, generator: str) -> None:
    """Both library consumers build from source, recover missing libraries and reuse cache."""
    backend = "ninja" if generator == "Ninja" else "make"
    if not all(shutil.which(tool) for tool in ("cmake", "cc", "ar", backend)):
        pytest.skip(f"cmake, a C compiler, ar and {backend} are required")
    if not (shutil.which("gmake") or shutil.which("make")):
        pytest.skip("GNU make is required to build the native Makefile fixture")

    archive = prepare_source(tmp_path)
    (tmp_path / "main.c").write_text(
        "#include <securec.h>\nint main(void) { return csec_probe() == 42 ? 0 : 1; }\n",
        encoding="utf-8",
    )
    (tmp_path / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.16)\n"
        "project(CsecConsumer C)\n"
        'set(CANN_3RD_LIB_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cache")\n'
        'include("${CMAKE_CURRENT_SOURCE_DIR}/csec.cmake")\n'
        "add_executable(static_consumer main.c)\n"
        "target_link_libraries(static_consumer PRIVATE c_sec_static)\n"
        "add_executable(shared_consumer main.c)\n"
        "target_link_libraries(shared_consumer PRIVATE c_sec)\n",
        encoding="utf-8",
    )
    build = tmp_path / "build"
    library_dir = tmp_path / "cache" / "lib_cache" / "csec" / "lib"
    run_command("cmake", "-S", str(tmp_path), "-B", str(build), "-G", generator)
    run_command("cmake", "--build", str(build), "--parallel", "2")
    for name in ("static_consumer", "shared_consumer"):
        run_command(str(build / name), library_dir=library_dir)

    if generator == "Ninja":
        # Each imported library independently recovers through its producing step.
        for library in ("libc_sec.a", "libc_sec.so"):
            installed = library_dir / library
            installed.unlink()
            run_command("cmake", "--build", str(build), "--parallel", "2")
            assert installed.is_file()
            for name in ("static_consumer", "shared_consumer"):
                run_command(str(build / name), library_dir=library_dir)

    # Reconfigure without the source archive to exercise binary cache reuse.
    archive.unlink()
    cached_build = tmp_path / "cached-build"
    output = run_command(
        "cmake", "-S", str(tmp_path), "-B", str(cached_build), "-G", generator
    )
    assert "[ThirdParty][csec] use cache:" in output
    run_command("cmake", "--build", str(cached_build), "--parallel", "2")
    for name in ("static_consumer", "shared_consumer"):
        run_command(str(cached_build / name), library_dir=library_dir)
