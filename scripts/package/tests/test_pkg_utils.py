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

import pytest

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
