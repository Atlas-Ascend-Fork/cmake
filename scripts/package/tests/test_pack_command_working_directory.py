# -----------------------------------------------------------------------------------------------------------
# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.
# -----------------------------------------------------------------------------------------------------------
"""使用真实子进程验证打包命令的交付目录。"""

import shlex
import sys
import zipfile

import pytest

from .. import packer


@pytest.mark.parametrize(
    "directory_name", ["staging", "staging with spaces", "staging's files", "交付 目录"]
)
def test_pack_command_writes_in_requested_delivery_directory(tmp_path, directory_name):
    delivery = tmp_path.resolve() / directory_name
    delivery.mkdir()
    (delivery / "payload.txt").write_text("package payload", encoding="utf-8")
    command = shlex.join(
        [
            sys.executable,
            "-c",
            "from pathlib import Path; import zipfile; "
            "archive = zipfile.ZipFile('package.zip', 'w'); "
            "archive.write('payload.txt'); archive.close()",
        ]
    )
    result = packer.exec_pack_cmd(str(delivery), command, "package.zip")
    assert result == "package.zip"

    with zipfile.ZipFile(delivery / "package.zip") as archive:
        assert archive.read("payload.txt") == b"package payload"
