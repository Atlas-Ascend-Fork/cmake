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

"""切换到解压目录重打包时，makeself 路径仍以调用目录为基准。"""

import argparse
from pathlib import Path

import pytest

from .. import mix_multi_arch_run_pkgs as mix

MAKESELF_FIXTURE = r"""#!/bin/bash
set -eu
test "$1" = --header
test "$(cat "$2")" = header-content
source_dir=${@: -4:1}
output=${@: -3:1}
cat "$source_dir/payload.bin" > "$output"
"""


@pytest.mark.parametrize(
    "path_kind",
    [
        "absolute",
        "relative",
        "spaces",
        "current",
        "parent",
        "symlink",
        "symlink-parent",
    ],
)
def test_repack_resolves_makeself_from_invocation_directory(
    tmp_path, monkeypatch, path_kind
):
    invocation_dir = tmp_path / "workspace"
    invocation_dir.mkdir()
    if path_kind == "current":
        tool_dir = invocation_dir
    elif path_kind == "parent":
        tool_dir = tmp_path / "tools"
    elif path_kind in {"symlink", "symlink-parent"}:
        tool_dir = tmp_path / "external" / "tools"
    elif path_kind == "spaces":
        tool_dir = invocation_dir / "tools with spaces"
    else:
        tool_dir = invocation_dir / "tools"
    tool_dir.mkdir(parents=True, exist_ok=True)
    (tool_dir / "makeself.sh").write_text(MAKESELF_FIXTURE, encoding="utf-8")
    (tool_dir / "makeself-header.sh").write_text("header-content", encoding="utf-8")
    tool_arg = {
        "absolute": str(tool_dir),
        "relative": "tools",
        "spaces": "tools with spaces",
        "current": ".",
        "parent": "../tools",
        "symlink": "tool-link",
        "symlink-parent": "tool-link/..",
    }[path_kind]
    if path_kind in {"symlink", "symlink-parent"}:
        link_target = tool_dir
        if path_kind == "symlink-parent":
            link_target = tool_dir / "child"
            link_target.mkdir()
        (invocation_dir / "tool-link").symlink_to(link_target, target_is_directory=True)
    monkeypatch.chdir(invocation_dir)

    package = Path("packages") / "sample.run"
    extract_dir = package.with_suffix("")
    info_dir = extract_dir / "share" / "info" / "sample"
    mix.generate_record_file([], str(info_dir / "RECORD"))
    mix.generate_filelist([], str(info_dir / "script" / "filelist.csv"))
    (info_dir / "scene.info").write_text("arch=x86_64\n", encoding="utf-8")
    payload = b"mixed-package-payload\x00\xff"
    (extract_dir / "payload.bin").write_bytes(payload)
    package.write_bytes(b"original-package")

    parser = argparse.ArgumentParser()
    mix.MixCommand.add_parser(parser.add_subparsers())
    args = parser.parse_args(
        ["mix", str(package), str(package), "--makeself", tool_arg]
    )
    assert args.makeself == str(tool_dir.resolve())
    assert mix.MixCommand(args).check_args()
    prepare = mix.Prepare(str(package), mix.Logger(print, print, print))
    operation = mix.Mix(prepare, prepare.get_scene_info(), args.makeself)

    assert operation.repack_run()
    assert package.read_bytes() == payload
    assert not package.with_name("sample.mixed.run").exists()


@pytest.mark.parametrize("missing", ["directory", "makeself.sh", "makeself-header.sh"])
def test_cli_rejects_missing_makeself_tools(tmp_path, monkeypatch, missing):
    monkeypatch.chdir(tmp_path)
    packages = ["a.run", "b.run"]
    for package in packages:
        Path(package).write_bytes(b"original-package")
    tool_dir = Path("tools")
    if missing != "directory":
        tool_dir.mkdir()
        for name in ["makeself.sh", "makeself-header.sh"]:
            if name != missing:
                (tool_dir / name).touch()

    def unexpected_mix(*_args):
        pytest.fail("Invalid tools must be rejected before extracting packages")

    monkeypatch.setattr(mix.MixCommand, "mix_process", unexpected_mix)

    assert mix.main(["mix", *packages, "--makeself", str(tool_dir)]) == 1
