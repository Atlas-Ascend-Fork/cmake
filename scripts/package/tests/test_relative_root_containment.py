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

"""词法包含关系及真实 filelist 消费方回归。"""

import pytest

from ..filelist import (
    FileItemRelation,
    convert_nested_path_in_filelist,
    create_file_item,
    is_nested_file_item,
)
from ..utils.pkg_utils import is_subdirectory


@pytest.mark.parametrize(
    "base,child,expected",
    [
        (".", "include", True),
        (".", "./include", True),
        (".", ".", True),
        (".", "a/../include", True),
        (".", "../escape", False),
        ("pkg", "pkg/include", True),
        ("pkg", "pkg-other/include", False),
        ("pkg", "pkg/../escape", False),
        ("pkg", "pkg", True),
        ("/", "/include", True),
        ("/pkg", "/pkg/include", True),
        ("/pkg", "/pkg-other", False),
        (".", "/include", False),
        ("/pkg", "pkg/include", False),
    ],
)
def test_lexical_containment(base, child, expected):
    assert is_subdirectory(base, child) is expected


def test_no_symlink_resolution(tmp_path):
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "link").symlink_to(outside, target_is_directory=True)
    assert is_subdirectory(str(root), str(root / "link/file"))


def _item(path, is_dir):
    return create_file_item(
        "mod",
        "copy",
        path,
        path,
        "N",
        "644",
        "root:root",
        "all",
        [],
        set(),
        "N",
        "FALSE",
        "",
        "block",
        [],
        set(),
        is_dir,
    )


def test_relative_root_classification_and_conversion():
    root, child = _item(".", True), _item("include", True)
    assert is_nested_file_item(child, root) == FileItemRelation.NESTED
    assert is_nested_file_item(root, root) == FileItemRelation.SAME
    converted = list(convert_nested_path_in_filelist([root, child]))
    assert converted == [root, child._replace(operation="del")]
