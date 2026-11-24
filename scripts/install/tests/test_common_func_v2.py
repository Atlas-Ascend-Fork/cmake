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
import subprocess
import textwrap
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("filelist", ["fail\nok", "ok\nfail"])
@pytest.mark.parametrize("use_fifo", [False, True])
def test_foreach_filelist_exec_reports_worker_failure(tmp_path, filelist, use_fifo):
    """任一并发任务失败时，整体操作应返回该失败状态。"""
    script = textwrap.dedent(
        """
        . scripts/install/common_func_v2.inc
        . scripts/install/common_func.inc

        if [ "${USE_FIFO}" = "true" ]; then
            fifo_path="${TEST_TMPDIR}/parallel.fifo"
            mkfifo "${fifo_path}"
            exec 8<> "${fifo_path}"
            rm -f "${fifo_path}"
            printf '\\n\\n' >&8
            PARALLEL_FIFO="${fifo_path}"
        else
            PARALLEL_FIFO="none"
        fi

        worker_result() {
            if [ "$1" = "fail" ]; then
                return 7
            fi
            return 0
        }

        worker() {
            exec_with_param "$3" worker_result "$2"
        }

        foreach_filelist_exec "${FILELIST}" no concurrency worker /tmp
        status="$?"
        if [ "${USE_FIFO}" = "true" ]; then
            exec 8>&-
        fi
        exit "${status}"
        """
    )
    env = os.environ.copy()
    env.update(
        {
            "FILELIST": filelist,
            "TEST_TMPDIR": str(tmp_path),
            "USE_FIFO": str(use_fifo).lower(),
        }
    )

    result = subprocess.run(
        ["sh", "-c", script],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 7, result.stderr
