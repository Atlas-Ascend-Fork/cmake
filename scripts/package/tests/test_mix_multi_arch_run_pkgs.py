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

import os
from argparse import Namespace
from unittest.mock import patch

import pytest

from package import mix_multi_arch_run_pkgs as mix_module
from package.mix_multi_arch_run_pkgs import MixCommand


class TestMixCommand:
    @pytest.mark.parametrize(
        "test_item",
        [
            {
                "pkgs": ["a.run"],
                "expected": True,
            },
            {
                "pkgs": [".run"],
                "expected": False,
            },
            {
                "pkgs": ["..run"],
                "expected": False,
            },
            {
                "pkgs": ["...run"],
                "expected": False,
            },
            {
                "pkgs": ["a...run"],
                "expected": True,
            },
            {
                "pkgs": ["a.txt"],
                "expected": False,
            },
        ],
    )
    def test_check_args_pkgs_suffix_check(self, test_item):
        args = Namespace(**test_item)
        with patch.object(os.path, "exists", return_value=True):
            result = MixCommand(args)._check_args_pkgs()
        assert args.expected == result


def run_mix_with_repack_results(monkeypatch, repack_results):
    """Run the CLI flow with mocked package operations."""
    repack_calls = []

    class FakePrepare:
        def __init__(self, filepath, logger):
            self.arch = "aarch64" if filepath == "a.run" else "x86_64"

        def decompress_run(self):
            pass

        def get_scene_info(self):
            return mix_module.SceneInfo(self.arch, f"/{self.arch}/scene.info")

    class FakeMix:
        def __init__(self, prepare, scene_info, makeself_dir):
            self.scene_info = scene_info

        def mix_artifacts(self, other):
            return True

        def repack_run(self):
            repack_calls.append(self.scene_info.arch)
            return repack_results[self.scene_info.arch]

    monkeypatch.setattr(mix_module, "Prepare", FakePrepare)
    monkeypatch.setattr(mix_module, "Mix", FakeMix)
    monkeypatch.setattr(mix_module.MixCommand, "check_args", lambda self: True)

    exit_code = mix_module.main(["mix", "a.run", "b.run", "--makeself", "unused"])
    return exit_code, repack_calls


def test_repack_failures_propagate_to_cli_and_try_both_architectures(monkeypatch):
    """A failed repack on either architecture makes the CLI fail after trying both."""
    exit_code, repack_calls = run_mix_with_repack_results(
        monkeypatch, {"aarch64": False, "x86_64": False}
    )

    assert exit_code == 1
    assert repack_calls == ["aarch64", "x86_64"]


def test_successful_repack_keeps_cli_success(monkeypatch):
    """Successful repacks on both architectures keep the CLI exit status at zero."""
    exit_code, repack_calls = run_mix_with_repack_results(
        monkeypatch, {"aarch64": True, "x86_64": True}
    )

    assert exit_code == 0
    assert repack_calls == ["aarch64", "x86_64"]
