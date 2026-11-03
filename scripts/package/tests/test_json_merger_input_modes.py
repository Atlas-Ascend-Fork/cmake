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
from .. import json_merger


@pytest.mark.parametrize(
    "inputs",
    [
        [],
        ["--base-file", "base.json"],
        ["--update-file", "update.json"],
        ["--input-files", "a.json", "--base-file", "base.json"],
    ],
)
def test_incomplete_or_ambiguous_mode(inputs, tmp_path):
    output = tmp_path / "out.json"
    with pytest.raises(SystemExit) as error:
        json_merger.main([*inputs, "--output-file", str(output)])
    assert error.value.code == 2
    assert not output.exists()


@pytest.mark.parametrize(
    "inputs", [["--base-file", "a", "--update-file", "b"], ["--input-files", "a", "b"]]
)
def test_valid_modes(inputs):
    assert json_merger.parse_args([*inputs, "--output-file", "out.json"])
