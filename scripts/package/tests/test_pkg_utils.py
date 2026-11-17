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

import pytest

from package.utils import pkg_utils
from package.utils.pkg_utils import get_path_ext, get_path_without_ext, is_subdirectory


@pytest.mark.parametrize(
    "test_item",
    [
        {
            "base": "x86_64-linux",
            "sub": "x86_64-linux",
            "expected": True,
        },
        {
            "base": "x86_64-linux",
            "sub": "x86_64-linux/include",
            "expected": True,
        },
        {
            "base": "x86_64-linux",
            "sub": "x86_64-linux-2",
            "expected": False,
        },
        {
            "base": "x86_64-linux/include",
            "sub": "include/acl",
            "expected": False,
        },
        {
            "base": "x86_64-linux/../include",
            "sub": "include/acl",
            "expected": True,
        },
        {
            "base": "x86_64-linux",
            "sub": "x86_64-linux/../include",
            "expected": False,
        },
    ],
)
def test_is_subdirectory(test_item):
    base = test_item["base"]
    sub = test_item["sub"]
    expected = test_item["expected"]
    assert is_subdirectory(base, sub) == expected


@pytest.mark.parametrize(
    "test_item",
    [
        {
            "path": "a.run",
            "expected": "a",
        },
        {
            "path": ".run",
            "expected": ".run",
        },
        {
            "path": "..run",
            "expected": "..run",
        },
        {
            "path": "...run",
            "expected": "...run",
        },
        {
            "path": "a...run",
            "expected": "a..",
        },
        {
            "path": "b.txt",
            "expected": "b",
        },
    ],
)
def test_get_path_without_ext(test_item):
    path = test_item["path"]
    expected = test_item["expected"]
    assert expected == get_path_without_ext(path)


@pytest.mark.parametrize(
    "test_item",
    [
        {
            "path": "a.run",
            "expected": ".run",
        },
        {
            "path": ".run",
            "expected": "",
        },
        {
            "path": "..run",
            "expected": "",
        },
        {
            "path": "...run",
            "expected": "",
        },
        {
            "path": "a...run",
            "expected": ".run",
        },
        {
            "path": "b.txt",
            "expected": ".txt",
        },
    ],
)
def test_get_path_ext(test_item):
    path = test_item["path"]
    expected = test_item["expected"]
    assert expected == get_path_ext(path)


def test_pkg_utils_basic_helpers_and_errors():
    assert list(pkg_utils.flatten([[1], [2, 3]])) == [1, 2, 3]
    merged = pkg_utils.merge_dict({"a": 1}, {"b": 2})
    assert merged == {"a": 1, "b": 2}

    def add(x, y):
        return x + y

    sp = pkg_utils.star_pipe(lambda a, b: (a + 1, b + 1), add)
    assert sp(1, 2) == 5

    swapped = pkg_utils.swap_args(lambda x, y: x - y)
    assert swapped(1, 3) == 2  # 实际执行 3 - 1

    cf = pkg_utils.config_feature_to_set("f1;f2", "feature")
    assert cf == {"f1", "f2"}
    assert pkg_utils.config_feature_to_string(set()) == "all"
    assert pkg_utils.config_feature_to_string({"b", "a"}) == "a;b"

    # 错误分支：空字符串 / all
    with pytest.raises(pkg_utils.PackageConfigError):
        pkg_utils.config_feature_to_set("", "feature")
    with pytest.raises(pkg_utils.PackageConfigError):
        pkg_utils.config_feature_to_set("all", "feature")

    # conditional_apply / pairwise / path_join / yield_if
    fn = pkg_utils.conditional_apply(lambda x: x > 0, lambda x: x + 1)
    assert fn(1) == 2 and fn(0) == 0

    seq = [1, 2, 3]
    pairs = list(pkg_utils.pairwise(seq))
    assert pairs == [(1, 2), (2, 3)]

    assert pkg_utils.path_join(None, "a") is None
    assert pkg_utils.path_join("base", "a", "b").endswith(
        "base" + os.sep + "a" + os.sep + "b"
    )

    yielded = list(pkg_utils.yield_if(1, lambda x: x == 1))
    assert yielded == [1]
