#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (c) 2025 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

# **************************************************************
# 签名脚本：调用 signatrust_client 对指定文件制作 CMS (p7s) detached 签名
# 流程：准备 CRL（本地优先，否则下载）→ 逐文件签名 → 校验 p7s 生成
#
# 调用方式：
#   python3 community_sign_build.py <file1> [file2 ...]
#   argv[1:] = 待签名文件列表
# **************************************************************

from unittest.mock import Mock
import community_sign_build as signing


def test_http_failure_retries_and_does_not_accept_error_body(tmp_path, monkeypatch):
    monkeypatch.delenv("CRL_FILE_PATH", raising=False)
    monkeypatch.setattr(signing, "_sleep_backoff", lambda _: None)
    calls = []

    def curl(command, **kwargs):
        calls.append(command)
        # curl --fail reports HTTP failures even if an old/error file is present.
        (tmp_path / signing.CRL_FILENAME).write_text("<html>404 Not Found</html>")
        return Mock(returncode=22 if "--fail" in command else 0)

    monkeypatch.setattr(signing.subprocess, "run", curl)
    assert signing.prepare_crl(str(tmp_path)) is None
    assert len(calls) == signing.CRL_DOWNLOAD_RETRIES
    assert all("--fail" in command for command in calls)
    assert not (tmp_path / signing.CRL_FILENAME).exists()
