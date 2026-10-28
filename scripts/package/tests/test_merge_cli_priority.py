# -----------------------------------------------------------------------------------------------------------
# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.
# -----------------------------------------------------------------------------------------------------------

"""双文件和批量命令行必须使用相同的合并优先级。"""

import json
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("script", ["merge_binary_info_config.py", "json_merger.py"])
@pytest.mark.parametrize("priority", ["first", "last", None])
@pytest.mark.parametrize("mode", ["pair", "batch"])
def test_cli_merge_priority(tmp_path: Path, script: str, priority, mode: str):
    inputs = []
    binary_config = script == "merge_binary_info_config.py"
    for tag in ("base", "update"):
        if binary_config:
            content = {
                "Add": {"opFile": tag, "binaryList": [{"binaryPath": tag + ".o"}]}
            }
        else:
            content = {"tag": tag, "binList": [tag + ".o"]}
        path = tmp_path / (tag + ".json")
        path.write_text(json.dumps(content), encoding="utf-8")
        inputs.append(path)
    output = tmp_path / "output" / "merged.json"
    command = [sys.executable, str(Path(__file__).resolve().parents[1] / script)]
    if mode == "pair":
        command.extend(["--base-file", str(inputs[0]), "--update-file", str(inputs[1])])
    else:
        command.extend(["--input-files", *(str(path) for path in inputs)])
    command.extend(["--output-file", str(output)])
    if priority is not None:
        command.extend(["--priority", priority])
    completed = subprocess.run(command, capture_output=True, text=True, timeout=10)
    assert completed.returncode == 0, completed.stderr
    merged = json.loads(output.read_text(encoding="utf-8"))
    # 批量模式既有约定：first 反转拼接顺序，last（默认）保持输入顺序。
    order = ["update.o", "base.o"] if priority == "first" else ["base.o", "update.o"]
    if binary_config:
        assert merged == {
            "Add": {
                "opFile": "base" if priority == "first" else "update",
                "binaryList": [{"binaryPath": value} for value in order],
            }
        }
    else:
        # 保留 json_merger 既有的其他字段选择行为。
        assert merged == {
            "tag": "update" if priority == "first" else "base",
            "binList": order,
        }


@pytest.mark.parametrize(
    "provided", [[], ["--base-file", "missing.json"], ["--update-file", "missing.json"]]
)
def test_binary_config_incomplete_cli_reports_argument_error_without_overwriting(
    tmp_path, provided
):
    output = tmp_path / "existing.json"
    output.write_text('{"preserved": true}', encoding="utf-8")
    script = Path(__file__).resolve().parents[1] / "merge_binary_info_config.py"
    result = subprocess.run(
        [sys.executable, str(script), *provided, "--output-file", str(output)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert "error:" in result.stderr and "Traceback" not in result.stderr
    assert output.read_text(encoding="utf-8") == '{"preserved": true}'


def test_binary_config_save_accepts_current_directory_output(tmp_path, monkeypatch):
    from .. import merge_binary_info_config

    monkeypatch.chdir(tmp_path)
    merge_binary_info_config.save_json_file("result.json", {"Add": {"binaryList": []}})
    assert json.loads((tmp_path / "result.json").read_text(encoding="utf-8")) == {
        "Add": {"binaryList": []}
    }
