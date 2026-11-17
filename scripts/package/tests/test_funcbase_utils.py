#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

# -----------------------------------------------------------------------------------------------------------
# Copyright (c) 2025 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.
# -----------------------------------------------------------------------------------------------------------

"""Tests for funcbase utility functions."""

from package.utils import funcbase


class TestDispatchExtended:
    """Extended tests for dispatch."""

    @staticmethod
    def test_dispatch_basic():
        """Test dispatch function."""
        func = funcbase.dispatch(lambda x: x * 2, lambda x: x + 1)
        # dispatch returns a generator
        result = list(func(5))
        # Should apply all functions
        assert 10 in result  # 5 * 2
        assert 6 in result  # 5 + 1


class TestPipeExtended:
    """Extended tests for pipe."""

    @staticmethod
    def test_pipe_basic():
        """Test pipe function."""
        func = funcbase.pipe(lambda x: x * 2, lambda x: x + 1)
        result = func(5)
        assert result == 11  # (5 * 2) + 1


class TestInvokeExtended:
    """Extended tests for invoke."""

    @staticmethod
    def test_invoke_basic():
        """Test invoke function."""
        result = funcbase.invoke(list, iter([1, 2, 3]))
        assert result == [1, 2, 3]


def test_funcbase_basic_helpers_and_high_order():
    const_f = funcbase.constant(10)
    assert const_f() == 10

    def plus1(x):
        return x + 1

    def mul2(x):
        return x * 2

    pipe_f = funcbase.pipe(plus1, mul2)
    assert pipe_f(3) == 8

    ident = funcbase.identity("x")
    assert ident == "x"

    # dispatch / invoke / side_effect / star_apply / any_ / not_
    d = funcbase.dispatch(lambda x: x + 1, lambda x: x + 2)
    assert list(d(1)) == [2, 3]

    assert funcbase.invoke(lambda x, y: x + y, 1, 2) == 3

    calls = []

    def rec(x):
        calls.append(x)

    se = funcbase.side_effect(rec)
    assert se(5) == 5 and calls == [5]

    sa = funcbase.star_apply(lambda a, b: a + b)
    assert sa((1, 2)) == 3

    any_f = funcbase.any_(lambda x: False, lambda x: x > 0)
    assert any_f(1) is True

    not_f = funcbase.not_(lambda x: x > 0)
    assert not_f(0) is True and not_f(1) is False
