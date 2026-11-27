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

"""Tests for generate_version_info.py."""

import json
import logging
import subprocess
import sys
from pathlib import Path

import pytest

import generate_version_info


class TestGenVersionInfoContent:
    """Tests for gen_version_info_content function."""

    @staticmethod
    def test_basic_content_no_deps(monkeypatch):
        """Test generating content without dependencies and without tagInfo env var."""
        monkeypatch.delenv("tagInfo", raising=False)

        content = list(generate_version_info.gen_version_info_content("1.0.0", []))

        assert content[0] == "Version=1.0.0"
        assert content[1] == "version_dir=cann"
        assert content[-2].startswith("timestamp=")
        assert content[-1] == ""

    @staticmethod
    def test_content_with_single_dep(monkeypatch):
        """Test generating content with a single dependency pair."""
        monkeypatch.delenv("tagInfo", raising=False)

        content = list(
            generate_version_info.gen_version_info_content("2.0.0", ["pkg1", "1.1.0"])
        )

        assert content[0] == "Version=2.0.0"
        assert content[1] == "version_dir=cann"
        assert content[2] == 'required_package_pkg1_version="1.1.0"'
        assert content[-2].startswith("timestamp=")
        assert content[-1] == ""

    @staticmethod
    def test_content_with_multiple_deps(monkeypatch):
        """Test generating content with multiple dependency pairs."""
        monkeypatch.delenv("tagInfo", raising=False)

        deps = ["pkg1", "1.0.0", "pkg2", "2.0.0", "pkg3", "3.0.0"]
        content = list(generate_version_info.gen_version_info_content("3.0.0", deps))

        assert content[0] == "Version=3.0.0"
        assert content[1] == "version_dir=cann"
        assert content[2] == 'required_package_pkg1_version="1.0.0"'
        assert content[3] == 'required_package_pkg2_version="2.0.0"'
        assert content[4] == 'required_package_pkg3_version="3.0.0"'
        assert content[-2].startswith("timestamp=")
        assert content[-1] == ""

    @staticmethod
    def test_timestamp_from_taginfo_env(monkeypatch):
        """Test generating timestamp from tagInfo environment variable."""
        monkeypatch.setenv("tagInfo", "release_20250115_120000_abc123")

        content = list(generate_version_info.gen_version_info_content("1.0.0", []))

        # Extract timestamp line
        timestamp_line = [line for line in content if line.startswith("timestamp=")][0]
        assert timestamp_line == "timestamp=20250115_120000"

    @staticmethod
    def test_timestamp_from_taginfo_with_multiple_underscores(monkeypatch):
        """Test extracting timestamp from tagInfo with multiple underscore segments."""
        monkeypatch.setenv("tagInfo", "my_release_package_20250304_101030_xyz789")

        content = list(generate_version_info.gen_version_info_content("1.0.0", []))

        timestamp_line = [line for line in content if line.startswith("timestamp=")][0]
        # Should take 3rd and 2nd from last segments
        assert timestamp_line == "timestamp=20250304_101030"

    @staticmethod
    def test_timestamp_from_current_time_when_no_taginfo(monkeypatch):
        """Test timestamp is generated from current time when tagInfo is not set."""
        monkeypatch.delenv("tagInfo", raising=False)

        content = list(generate_version_info.gen_version_info_content("1.0.0", []))

        timestamp_line = [line for line in content if line.startswith("timestamp=")][0]
        timestamp = timestamp_line.split("=")[1]
        assert len(timestamp) == 18  # YYYYmmdd_HHMMSS + 3 millisecond digits

    @staticmethod
    def test_empty_deps_list(monkeypatch):
        """Test with empty deps list - should not generate any required_package lines."""
        monkeypatch.delenv("tagInfo", raising=False)

        content = list(generate_version_info.gen_version_info_content("1.0.0", []))

        # Should have: Version, version_dir, timestamp, and empty line
        assert len(content) == 4
        assert content[0] == "Version=1.0.0"
        assert content[1] == "version_dir=cann"
        assert content[-2].startswith("timestamp=")
        assert content[-1] == ""


class TestMain:
    """Tests for main function."""

    @staticmethod
    def test_main_success_with_deps(tmp_path: Path, monkeypatch):
        """Test main function success with dependencies."""
        output_file = TestMain._setup_main_test(
            monkeypatch, tmp_path, "1.2.3", deps=["dep1", "1.0.0", "dep2", "2.0.0"]
        )

        result = generate_version_info.main()

        assert result is True
        assert output_file.exists()
        content = output_file.read_text(encoding="utf-8")
        assert "Version=1.2.3" in content
        assert "version_dir=cann" in content
        assert 'required_package_dep1_version="1.0.0"' in content
        assert 'required_package_dep2_version="2.0.0"' in content
        assert "timestamp=" in content

    @staticmethod
    def test_main_success_no_deps(tmp_path: Path, monkeypatch):
        """Test main function success without dependencies."""
        output_file = TestMain._setup_main_test(monkeypatch, tmp_path, "3.0.0")

        result = generate_version_info.main()

        assert result is True
        assert output_file.exists()
        content = output_file.read_text(encoding="utf-8")
        assert "Version=3.0.0" in content
        assert "version_dir=cann" in content
        assert "required_package_" not in content
        assert "timestamp=" in content

    @staticmethod
    def test_main_error_odd_number_of_deps(tmp_path: Path, monkeypatch):
        """Test main function returns False when deps has odd number of elements."""
        output_file = TestMain._setup_main_test(
            monkeypatch,
            tmp_path,
            "1.0.0",
            deps=["dep1", "1.0.0", "dep2"],  # 3 elements - odd number
        )

        result = generate_version_info.main()

        assert result is False
        # File should not be created when there's an error
        assert not output_file.exists()

    @staticmethod
    def test_main_with_single_dep_pair(tmp_path: Path, monkeypatch):
        """Test main with exactly one dependency pair."""
        output_file = TestMain._setup_main_test(
            monkeypatch, tmp_path, "2.0.0", deps=["single_dep", "1.5.0"]
        )

        result = generate_version_info.main()

        assert result is True
        content = output_file.read_text(encoding="utf-8")
        assert 'required_package_single_dep_version="1.5.0"' in content

    @staticmethod
    def test_main_output_file_ends_with_newline(tmp_path: Path, monkeypatch):
        """Test that output file ends with a newline."""
        output_file = TestMain._setup_main_test(monkeypatch, tmp_path, "1.0.0")

        generate_version_info.main()

        content = output_file.read_bytes()
        # Content should end with newline
        assert content.endswith(b"\n")

    @staticmethod
    def _setup_main_test(
        monkeypatch, tmp_path, version, deps=None, output_file_name="version.info"
    ):
        """Helper method to setup main function test."""
        monkeypatch.delenv("tagInfo", raising=False)
        output_file = tmp_path / output_file_name

        args = ["generate_version_info.py", version]
        if deps:
            args.extend(deps)
        args.extend(["--output", str(output_file)])

        monkeypatch.setattr("sys.argv", args)
        return output_file


class TestMainEntryPoint:
    """Tests for main entry point."""

    @staticmethod
    def test_main_entry_point_success(tmp_path: Path, monkeypatch):
        """Test __main__ entry point with successful execution."""
        TestMainEntryPoint._run_main_entry_point(monkeypatch, tmp_path, "1.0.0")

        # main() returns True and sys.exit(True) will exit with 0
        # but we can just verify main returns True
        result = generate_version_info.main()
        assert result is True

    @staticmethod
    def test_main_entry_point_failure(tmp_path: Path, monkeypatch):
        """Test __main__ entry point with failed execution (odd deps)."""
        TestMainEntryPoint._run_main_entry_point(
            monkeypatch,
            tmp_path,
            "1.0.0",
            deps=["dep1", "1.0.0", "dep2"],  # odd number of deps
        )

        result = generate_version_info.main()
        assert result is False

    @staticmethod
    def _run_main_entry_point(monkeypatch, tmp_path, version, deps=None):
        """Helper to run main entry point test."""
        monkeypatch.delenv("tagInfo", raising=False)
        output_file = tmp_path / "version.info"

        args = ["generate_version_info.py", version]
        if deps:
            args.extend(deps)
        args.extend(["--output", str(output_file)])

        monkeypatch.setattr("sys.argv", args)
        return output_file


class TestScriptAsMain:
    """Tests running the script as __main__ using subprocess."""

    @staticmethod
    def test_script_success_exit_code(tmp_path: Path):
        """Test script exits with code 0 on success."""
        output_file = tmp_path / "version.info"
        script_path = Path(generate_version_info.__file__)

        result = subprocess.run(
            [sys.executable, str(script_path), "1.0.0", "--output", str(output_file)],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert output_file.exists()

    @staticmethod
    def test_script_failure_exit_code(tmp_path: Path):
        """Test script exits with code 1 on failure (odd deps)."""
        output_file = tmp_path / "version.info"
        script_path = Path(generate_version_info.__file__)

        result = subprocess.run(
            [
                sys.executable,
                str(script_path),
                "1.0.0",
                "dep1",
                "1.0.0",
                "dep2",  # odd number of deps
                "--output",
                str(output_file),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1
        assert "error" in result.stderr.lower()


class TestLoadRepoInfoFile:
    """Tests for load_repo_info_file function (JSON schema)."""

    @staticmethod
    def _write(tmp_path: Path, data) -> Path:
        """写仓库信息文件：dict 用 json.dumps 序列化，str 原样写入（构造畸形 JSON）。"""
        info_file = tmp_path / "repo_info.json"
        if isinstance(data, str):
            info_file.write_text(data, encoding="utf-8")
        else:
            info_file.write_text(json.dumps(data, indent=4), encoding="utf-8")
        return info_file

    @staticmethod
    def test_valid_multiple_packages(tmp_path: Path):
        """Multiple packages should be parsed and kept raw (no normalization here)."""
        info_file = TestLoadRepoInfoFile._write(
            tmp_path,
            {
                "npu-runtime": {
                    "repository_url": "git@gitcode.com:cann/runtime.git",
                    "commit_id": "a" * 40,
                },
                "ge-executor": {
                    "repository_url": "https://gitcode.com/cann/ge",
                    "commit_id": "B" * 40,
                },
            },
        )

        info = generate_version_info.load_repo_info_file(str(info_file))

        assert info["npu-runtime"] == {
            "repository_url": "git@gitcode.com:cann/runtime.git",
            "commit_id": "a" * 40,
        }
        # 值原样透传：归一化与小写转换发生在生产者（gen_repo_info.py），消费者不转换
        assert info["ge-executor"]["commit_id"] == "B" * 40

    @staticmethod
    def test_unknown_key_rejected(tmp_path: Path):
        """Fields other than repository_url / commit_id should be rejected."""
        info_file = TestLoadRepoInfoFile._write(
            tmp_path, {"npu-runtime": {"branch": "master"}}
        )

        with pytest.raises(ValueError, match="Unknown field"):
            generate_version_info.load_repo_info_file(str(info_file))

    @staticmethod
    def test_missing_commit_id_rejected(tmp_path: Path):
        """Only one field of a package should be rejected (same in same out)."""
        info_file = TestLoadRepoInfoFile._write(
            tmp_path,
            {"npu-runtime": {"repository_url": "https://gitcode.com/cann/runtime"}},
        )

        with pytest.raises(ValueError, match="must define both"):
            generate_version_info.load_repo_info_file(str(info_file))

    @staticmethod
    def test_invalid_commit_id_rejected(tmp_path: Path):
        """Non 40-hex commit id should be rejected."""
        info_file = TestLoadRepoInfoFile._write(
            tmp_path,
            {
                "npu-runtime": {
                    "repository_url": "https://gitcode.com/cann/runtime",
                    "commit_id": "abc123",
                }
            },
        )

        with pytest.raises(ValueError, match="Invalid commit_id"):
            generate_version_info.load_repo_info_file(str(info_file))

    @staticmethod
    def test_empty_value_rejected(tmp_path: Path):
        """Empty value should be rejected."""
        info_file = TestLoadRepoInfoFile._write(
            tmp_path,
            {"npu-runtime": {"repository_url": "", "commit_id": "a" * 40}},
        )

        with pytest.raises(ValueError, match="Empty repository_url"):
            generate_version_info.load_repo_info_file(str(info_file))

    @staticmethod
    @pytest.mark.parametrize("field", ["repository_url", "commit_id"])
    def test_newline_in_value_rejected(tmp_path: Path, field):
        """Newline in values should be rejected to prevent line injection."""
        entry = {
            "repository_url": "https://gitcode.com/cann/runtime",
            "commit_id": "a" * 40,
        }
        entry[field] = entry[field] + "\nversion_dir=evil"
        info_file = TestLoadRepoInfoFile._write(tmp_path, {"npu-runtime": entry})

        with pytest.raises(ValueError, match="newline is not allowed"):
            generate_version_info.load_repo_info_file(str(info_file))

    @staticmethod
    def test_duplicate_top_level_key_rejected(tmp_path: Path):
        """Duplicate package key should be rejected instead of silently overriding."""
        info_file = TestLoadRepoInfoFile._write(
            tmp_path,
            "{"
            f'"npu-runtime": {{"commit_id": "{"a" * 40}"}}, '
            f'"npu-runtime": {{"commit_id": "{"b" * 40}"}}'
            "}",
        )

        with pytest.raises(ValueError, match=r"Duplicate JSON key 'npu-runtime' in "):
            generate_version_info.load_repo_info_file(str(info_file))

    @staticmethod
    def test_duplicate_field_rejected(tmp_path: Path):
        """Duplicate field inside one entry should be rejected."""
        info_file = TestLoadRepoInfoFile._write(
            tmp_path,
            "{"
            '"npu-runtime": {'
            '"repository_url": "https://gitcode.com/cann/runtime", '
            '"repository_url": "https://gitcode.com/cann/other"'
            f', "commit_id": "{"a" * 40}"'
            "}}",
        )

        with pytest.raises(ValueError, match="Duplicate JSON key"):
            generate_version_info.load_repo_info_file(str(info_file))

    @staticmethod
    def test_invalid_package_name_rejected(tmp_path: Path):
        """Package key with illegal characters should be rejected."""
        info_file = TestLoadRepoInfoFile._write(
            tmp_path,
            {"npu runtime": {"commit_id": "a" * 40}},
        )

        with pytest.raises(ValueError, match="Invalid package name"):
            generate_version_info.load_repo_info_file(str(info_file))

    @staticmethod
    def test_non_object_entry_rejected(tmp_path: Path):
        """Entry that is not a JSON object should be rejected."""
        info_file = TestLoadRepoInfoFile._write(
            tmp_path, {"npu-runtime": "https://gitcode.com/cann/runtime"}
        )

        with pytest.raises(ValueError, match="must be a JSON object"):
            generate_version_info.load_repo_info_file(str(info_file))

    @staticmethod
    def test_non_object_top_level_rejected(tmp_path: Path):
        """Top level that is not a JSON object should be rejected."""
        info_file = TestLoadRepoInfoFile._write(tmp_path, "[1, 2]")

        with pytest.raises(ValueError, match="must contain a JSON object"):
            generate_version_info.load_repo_info_file(str(info_file))

    @staticmethod
    def test_empty_json_is_valid(tmp_path: Path):
        """Empty object (producer empty state) should be accepted."""
        info_file = TestLoadRepoInfoFile._write(tmp_path, {})

        assert generate_version_info.load_repo_info_file(str(info_file)) == {}


class TestResolveRepoInfo:
    """Tests for resolve_repo_info function."""

    @staticmethod
    def test_entry_consumed_as_is(tmp_path: Path):
        """Entry values should be consumed as-is (processing is producer's job)."""
        info_file = tmp_path / "repo_info.json"
        info_file.write_text(
            json.dumps(
                {
                    "npu-runtime": {
                        "repository_url": "git@gitcode.com:cann/runtime.git",
                        "commit_id": "A" * 40,
                    }
                }
            ),
            encoding="utf-8",
        )

        result = generate_version_info.resolve_repo_info("npu-runtime", str(info_file))

        assert result == ("git@gitcode.com:cann/runtime.git", "A" * 40)

    @staticmethod
    def test_missing_package_entry_warns(tmp_path: Path, caplog):
        """Package absent in file should warn (with pkg name and path) and omit."""
        info_file = tmp_path / "repo_info.json"
        info_file.write_text(
            json.dumps(
                {
                    "other": {
                        "repository_url": "https://gitcode.com/cann/other",
                        "commit_id": "d" * 40,
                    }
                }
            ),
            encoding="utf-8",
        )

        with caplog.at_level(logging.WARNING):
            result = generate_version_info.resolve_repo_info(
                "npu-runtime", str(info_file)
            )

        assert result == (None, None)
        assert any(
            "not found in" in record.message
            and "npu-runtime" in record.message
            and str(info_file) in record.message
            for record in caplog.records
        )

    @staticmethod
    def test_empty_state_json_omits_fields(tmp_path: Path, caplog):
        """Producer empty state {} should omit fields with a warning."""
        info_file = tmp_path / "repo_info.json"
        info_file.write_text("{}", encoding="utf-8")

        with caplog.at_level(logging.WARNING):
            result = generate_version_info.resolve_repo_info(
                "npu-runtime", str(info_file)
            )

        assert result == (None, None)
        assert any("not found in" in record.message for record in caplog.records)

    @staticmethod
    def test_no_package_name_returns_none(tmp_path: Path):
        """Without package name the repo info should be skipped."""
        assert generate_version_info.resolve_repo_info(None, "whatever") == (
            None,
            None,
        )

    @staticmethod
    def test_no_repo_info_file_returns_none(tmp_path: Path):
        """Without repo info file the repo info should be skipped."""
        assert generate_version_info.resolve_repo_info("npu-runtime", None) == (
            None,
            None,
        )


class TestGenVersionInfoContentWithRepoInfo:
    """Tests for repo fields in gen_version_info_content."""

    @staticmethod
    def test_repo_fields_before_timestamp(monkeypatch):
        """Repo fields should be emitted before timestamp."""
        monkeypatch.delenv("tagInfo", raising=False)

        content = list(
            generate_version_info.gen_version_info_content(
                "1.0.0",
                ["dep", "1.0.0"],
                "https://gitcode.com/cann/runtime",
                "a" * 40,
            )
        )

        assert content.index(
            "repository_url=https://gitcode.com/cann/runtime"
        ) < content.index(f"commit_id={'a' * 40}")
        assert content.index(f"commit_id={'a' * 40}") < content.index(
            [line for line in content if line.startswith("timestamp=")][0]
        )
        assert content[-1] == ""

    @staticmethod
    def test_only_one_field_raises():
        """Only one repo field should raise ValueError."""
        with pytest.raises(ValueError, match="must be provided together"):
            list(
                generate_version_info.gen_version_info_content(
                    "1.0.0", [], repository_url="https://gitcode.com/cann/runtime"
                )
            )


class TestMainWithRepoInfo:
    """Tests for main function with repo info file."""

    @staticmethod
    def test_main_with_repo_info_file(tmp_path: Path, monkeypatch):
        """main should write repo fields before timestamp."""
        info_file = tmp_path / "repo_info.json"
        info_file.write_text(
            json.dumps(
                {
                    "npu-runtime": {
                        "repository_url": "https://gitcode.com/cann/runtime",
                        "commit_id": "e" * 40,
                    }
                }
            ),
            encoding="utf-8",
        )
        output_file = tmp_path / "version.info"
        monkeypatch.delenv("tagInfo", raising=False)
        monkeypatch.setattr(
            "sys.argv",
            [
                "generate_version_info.py",
                "1.0.0",
                "--output",
                str(output_file),
                "--package-name",
                "npu-runtime",
                "--repo-info-file",
                str(info_file),
            ],
        )

        result = generate_version_info.main()

        assert result is True
        lines = output_file.read_text(encoding="utf-8").splitlines()
        assert "repository_url=https://gitcode.com/cann/runtime" in lines
        assert f"commit_id={'e' * 40}" in lines
        assert (
            lines.index("repository_url=https://gitcode.com/cann/runtime")
            < lines.index(f"commit_id={'e' * 40}")
            < [i for i, line in enumerate(lines) if line.startswith("timestamp=")][0]
        )

    @staticmethod
    def test_main_missing_package_omits_repo_fields(
        tmp_path: Path, monkeypatch, caplog
    ):
        """Package absent from file should omit repo fields but still succeed."""
        info_file = tmp_path / "repo_info.json"
        info_file.write_text(
            json.dumps(
                {
                    "other": {
                        "repository_url": "https://gitcode.com/cann/other",
                        "commit_id": "d" * 40,
                    }
                }
            ),
            encoding="utf-8",
        )
        output_file = tmp_path / "version.info"
        monkeypatch.delenv("tagInfo", raising=False)
        monkeypatch.setattr(
            "sys.argv",
            [
                "generate_version_info.py",
                "1.0.0",
                "--output",
                str(output_file),
                "--package-name",
                "npu-runtime",
                "--repo-info-file",
                str(info_file),
            ],
        )

        with caplog.at_level(logging.WARNING):
            result = generate_version_info.main()

        assert result is True
        lines = output_file.read_text(encoding="utf-8").splitlines()
        assert not any(line.startswith("repository_url=") for line in lines)
        assert not any(line.startswith("commit_id=") for line in lines)
        assert any("not found in" in record.message for record in caplog.records)

    @staticmethod
    def test_main_invalid_repo_info_file_returns_false(tmp_path: Path, monkeypatch):
        """Repo info file violating schema should make main return False."""
        info_file = tmp_path / "repo_info.json"
        info_file.write_text(
            json.dumps({"npu-runtime": {"branch": "master"}}),
            encoding="utf-8",
        )
        output_file = tmp_path / "version.info"
        monkeypatch.setattr(
            "sys.argv",
            [
                "generate_version_info.py",
                "1.0.0",
                "--output",
                str(output_file),
                "--package-name",
                "npu-runtime",
                "--repo-info-file",
                str(info_file),
            ],
        )

        result = generate_version_info.main()

        assert result is False
        assert not output_file.exists()

    @staticmethod
    def test_main_invalid_json_returns_false(tmp_path: Path, monkeypatch, caplog):
        """Malformed JSON should make main return False with file path and line in error."""
        info_file = tmp_path / "repo_info.json"
        info_file.write_text("{not json", encoding="utf-8")
        output_file = tmp_path / "version.info"
        monkeypatch.setattr(
            "sys.argv",
            [
                "generate_version_info.py",
                "1.0.0",
                "--output",
                str(output_file),
                "--package-name",
                "npu-runtime",
                "--repo-info-file",
                str(info_file),
            ],
        )

        with caplog.at_level(logging.ERROR):
            result = generate_version_info.main()

        assert result is False
        assert not output_file.exists()
        # 错误信息必须带文件路径与行号（设计 4.6：行号仅 JSON 语法错误携带）
        assert any(
            str(info_file) in record.message and "line" in record.message
            for record in caplog.records
        )

    @staticmethod
    def test_main_with_repo_info_file_cli(tmp_path: Path):
        """CLI e2e: subprocess 运行脚本，带 --repo-info-file 与 --extra-field。"""
        info_file = tmp_path / "repo_info.json"
        info_file.write_text(
            json.dumps(
                {
                    "npu-runtime": {
                        "repository_url": "https://gitcode.com/cann/runtime",
                        "commit_id": "e" * 40,
                    }
                }
            ),
            encoding="utf-8",
        )
        output_file = tmp_path / "version.info"
        script_path = Path(generate_version_info.__file__)

        result = subprocess.run(
            [
                sys.executable,
                str(script_path),
                "1.0.0",
                "--output",
                str(output_file),
                "--package-name",
                "npu-runtime",
                "--repo-info-file",
                str(info_file),
                "--extra-field",
                "host_only=true",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert result.stderr == ""  # 成功路径无告警
        lines = output_file.read_text(encoding="utf-8").splitlines()
        assert lines[0] == "Version=1.0.0"
        assert (
            lines.index("repository_url=https://gitcode.com/cann/runtime")
            < lines.index(f"commit_id={'e' * 40}")
            < [i for i, line in enumerate(lines) if line.startswith("timestamp=")][0]
            < lines.index("host_only=true")
        )


class TestExtraFields:
    """Tests for EXTRA_FIELDS support."""

    @staticmethod
    def test_extra_fields_after_timestamp(monkeypatch):
        """Extra fields should be emitted after timestamp."""
        monkeypatch.delenv("tagInfo", raising=False)

        content = list(
            generate_version_info.gen_version_info_content(
                "1.0.0", [], extra_fields=["host_only=true"]
            )
        )

        assert content[-2] == "host_only=true"
        assert content[-1] == ""
        timestamp_index = [
            i for i, line in enumerate(content) if line.startswith("timestamp=")
        ][0]
        assert timestamp_index < content.index("host_only=true")

    @staticmethod
    def test_multiple_extra_fields_order(monkeypatch):
        """Multiple extra fields should keep their order."""
        monkeypatch.delenv("tagInfo", raising=False)

        content = list(
            generate_version_info.gen_version_info_content(
                "1.0.0", [], extra_fields=["a=1", "b=2"]
            )
        )

        assert content[-3:] == ["a=1", "b=2", ""]

    @staticmethod
    @pytest.mark.parametrize(
        "extra_field",
        [
            "Version=9.9.9",
            "version_dir=evil",
            "timestamp=19700101_000000",
            "repository_url=https://example.com",
            "commit_id=" + "a" * 40,
            'required_package_runtime_version="9.9.9"',
        ],
    )
    def test_reserved_extra_field_rejected(extra_field):
        """Reserved keys should not be injectable via extra fields."""
        with pytest.raises(ValueError, match="Reserved extra field"):
            list(
                generate_version_info.gen_version_info_content(
                    "1.0.0", [], extra_fields=[extra_field]
                )
            )

    @staticmethod
    def test_invalid_extra_field_rejected():
        """Extra field without key=value should be rejected."""
        with pytest.raises(ValueError, match="Invalid extra field"):
            list(
                generate_version_info.gen_version_info_content(
                    "1.0.0", [], extra_fields=["host_only"]
                )
            )

    @staticmethod
    def test_invalid_extra_field_with_next_line_rejected():
        """Extra field containing newline should be rejected."""
        with pytest.raises(ValueError, match="Invalid extra field"):
            list(
                generate_version_info.gen_version_info_content(
                    "1.0.0", [], extra_fields=["host_only=true\ninjected=x"]
                )
            )

    @staticmethod
    def test_invalid_extra_field_with_carriage_return_rejected():
        """Extra field containing carriage return should also be rejected."""
        with pytest.raises(ValueError, match="Invalid extra field"):
            list(
                generate_version_info.gen_version_info_content(
                    "1.0.0", [], extra_fields=["host_only=true\rinjected=x"]
                )
            )

    @staticmethod
    def test_main_with_extra_field(tmp_path: Path, monkeypatch):
        """main should append extra fields after timestamp."""
        output_file = tmp_path / "version.info"
        monkeypatch.delenv("tagInfo", raising=False)
        monkeypatch.setattr(
            "sys.argv",
            [
                "generate_version_info.py",
                "1.0.0",
                "--output",
                str(output_file),
                "--extra-field",
                "host_only=true",
            ],
        )

        result = generate_version_info.main()

        assert result is True
        lines = output_file.read_text(encoding="utf-8").splitlines()
        assert lines[-1] == "host_only=true"
        timestamp_index = [
            i for i, line in enumerate(lines) if line.startswith("timestamp=")
        ][0]
        assert timestamp_index < lines.index("host_only=true")
