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

from package.utils.pkg_utils import is_subdirectory


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
