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

"""Host cleanup regressions using real files, symlinks and Bash children."""

import os
from pathlib import Path

import pytest

from .. import mix_multi_arch_run_pkgs as mix

NAMES = ("extract", "extract output", "提取目录")
KINDS = ("directory_link", "file_link", "broken_link", "directory", "file", "absent")
RUN_FIXTURE = r"""#!/bin/bash
set -eu
test "$1" = --noexec
case "$2" in
    --extract=*) output=${2#--extract=} ;;
    *) exit 22 ;;
esac
mkdir -p "$output/share/info/test"
printf 'arch=x86_64\n' > "$output/share/info/test/scene.info"
printf 'fixture-payload\n' > "$output/artifact.bin"
"""


def make_target(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "payload.txt").write_bytes(b"original target\x00\xff")
    (target / "nested").mkdir()
    (target / "nested" / "data.bin").write_bytes(b"retain this target")
    return target


def snapshot(target):
    return {
        str(p.relative_to(target)): (p.read_bytes(), p.stat().st_mode)
        for p in target.rglob("*")
        if p.is_file()
    }


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("kind", KINDS)
def test_remove_real_paths_preserves_link_targets(tmp_path, name, kind):
    target = make_target(tmp_path)
    before = snapshot(target)
    path = tmp_path / name
    if kind == "directory_link":
        path.symlink_to(target, target_is_directory=True)
    elif kind == "file_link":
        path.symlink_to(target / "payload.txt")
    elif kind == "broken_link":
        path.symlink_to(tmp_path / "missing-target")
    elif kind == "directory":
        path.mkdir()
        (path / "own.bin").write_bytes(b"ordinary directory")
    elif kind == "file":
        path.write_bytes(b"ordinary file")
    mix.remove(str(path))
    assert not os.path.lexists(path)
    assert snapshot(target) == before


@pytest.mark.parametrize("name", NAMES)
def test_prepare_decompress_replaces_directory_link(tmp_path, name):
    target = make_target(tmp_path)
    before = snapshot(target)
    run_file = tmp_path / f"{name}.run"
    run_file.write_text(RUN_FIXTURE, encoding="utf-8")
    extract = tmp_path / name
    extract.symlink_to(target, target_is_directory=True)
    prepare = mix.Prepare(str(run_file), mix.Logger(print, print, print))
    prepare.decompress_run()
    assert extract.is_dir() and not extract.is_symlink()
    assert (extract / "artifact.bin").read_bytes() == b"fixture-payload\n"
    scene = prepare.get_scene_info()
    assert scene.arch == "x86_64"
    assert Path(scene.filepath) == extract / "share/info/test/scene.info"
    assert snapshot(target) == before


@pytest.mark.parametrize("name", NAMES)
def test_prepare_remove_extract_unlinks_directory_link(tmp_path, name):
    target = make_target(tmp_path)
    before = snapshot(target)
    extract = tmp_path / name
    extract.symlink_to(target, target_is_directory=True)
    prepare = mix.Prepare(
        str(tmp_path / f"{name}.run"), mix.Logger(print, print, print)
    )
    prepare.remove_extract()
    assert not os.path.lexists(extract)
    assert snapshot(target) == before
