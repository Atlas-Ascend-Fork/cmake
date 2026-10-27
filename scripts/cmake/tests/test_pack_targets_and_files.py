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

"""Regression tests for the CMake packaging helpers."""

import hashlib
import subprocess
import tarfile
import time
from pathlib import Path


CMAKE_ROOT = Path(__file__).resolve().parents[3]


def run_command(command: list[str]) -> None:
    """Run a command and surface its output if it fails."""
    subprocess.run(command, check=True, capture_output=True, text=True)


def read_archive_payload(archive_path: Path) -> str:
    """Read the payload packaged by cann_pack_targets_and_files."""
    with tarfile.open(archive_path, "r:gz") as archive:
        payload = archive.extractfile("./payload.txt")
        assert payload is not None
        with payload:
            return payload.read().decode("utf-8")


def read_archive_manifest(archive_path: Path) -> str:
    """Read the SHA256 manifest packaged by cann_pack_targets_and_files."""
    with tarfile.open(archive_path, "r:gz") as archive:
        manifest = archive.extractfile("./manifest.sha256")
        assert manifest is not None
        with manifest:
            return manifest.read().decode("utf-8")


def manifest_entry(payload: str) -> str:
    """Return the expected manifest line for a payload."""
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"payload.txt={digest}\n"


def test_files_changes_rebuild_archive(tmp_path: Path) -> None:
    """A changed FILES input must invalidate the generated archive."""
    source_dir = tmp_path / "source"
    build_dir = tmp_path / "build"
    source_dir.mkdir()
    (source_dir / "payload.txt").write_text("version-one\n", encoding="utf-8")
    (source_dir / "CMakeLists.txt").write_text(
        "\n".join(
            [
                "cmake_minimum_required(VERSION 3.16)",
                "project(PackFilesRegression NONE)",
                f'include("{CMAKE_ROOT / "function" / "prepare.cmake"}")',
                "cann_pack_targets_and_files(",
                '    OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/bundle.tar.gz"',
                "    OUTPUT_TARGET package",
                '    MANIFEST "manifest.sha256"',
                '    FILES "${CMAKE_CURRENT_SOURCE_DIR}/payload.txt"',
                ")",
                "",
            ]
        ),
        encoding="utf-8",
    )

    run_command(
        ["cmake", "-S", str(source_dir), "-B", str(build_dir), "-G", "Unix Makefiles"]
    )
    run_command(["cmake", "--build", str(build_dir)])
    archive_path = build_dir / "bundle.tar.gz"
    assert read_archive_payload(archive_path) == "version-one\n"
    assert read_archive_manifest(archive_path) == manifest_entry("version-one\n")

    time.sleep(1.1)
    (source_dir / "payload.txt").write_text("version-two\n", encoding="utf-8")
    run_command(["cmake", "--build", str(build_dir)])

    assert read_archive_payload(archive_path) == "version-two\n"
    assert read_archive_manifest(archive_path) == manifest_entry("version-two\n")
