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

from pathlib import Path


GUIDE_PATH = Path(__file__).resolve().parents[3] / "docs" / "scripts" / "sign-guide.md"


def test_header_only_examples_match_sign_flag_behavior():
    guide = GUIDE_PATH.read_text(encoding="utf-8")
    direct_section = guide.split("### 2. 直接调用脚本", maxsplit=1)[1].split(
        "\n### ", maxsplit=1
    )[0]
    workflow_section = guide.split("### 不签名模式（社区开发者常用）", maxsplit=1)[
        1
    ].split("\n### ", maxsplit=1)[0]

    assert (
        "python3 scripts/sign/add_header_sign.py /path/to/images true" in direct_section
    )
    assert "配置中的 type 留空" in direct_section
    assert (
        "python3 scripts/sign/add_header_sign.py /tmp/images true" in workflow_section
    )
    assert 'type=""' in workflow_section
    assert '| `"false"` | 任意 | 完全跳过，不执行任何操作 | 无 |' in guide
