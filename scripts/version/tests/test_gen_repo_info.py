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

"""Tests for gen_repo_info.py (default producer)."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import gen_repo_info


def _init_git_repo(repo: Path, message: str, remote_url: str = None) -> str:
    """初始化临时 git 仓库并创建一条空提交，返回 HEAD 提交号。"""
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=tester",
            "-c",
            "user.email=tester@example.com",
            "commit",
            "-q",
            "--allow-empty",
            "-F",
            "-",
        ],
        input=message,
        check=True,
        text=True,
    )
    if remote_url:
        subprocess.run(
            ["git", "-C", str(repo), "remote", "add", "origin", remote_url],
            check=True,
        )
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


requires_git = pytest.mark.skipif(
    shutil.which("git") is None, reason="git is not available"
)


class TestIsLocalRemote:
    """Tests for _is_local_remote classification."""

    @staticmethod
    @pytest.mark.parametrize(
        "url, expected",
        [
            ("/home/build/machine/path/repo", True),
            ("file:///home/build/machine/path/repo", True),
            # scp 语法 [user@]host:path，user 可省略
            ("host.example.com:cann/x.git", False),
            ("user@host.example.com:cann/x.git", False),
            ("git@gitcode.com:cann/runtime.git", False),
            ("ssh://git@gitcode.com:29418/cann/x.git", False),
            ("https://gitcode.com/cann/x.git", False),
        ],
    )
    def test_local_remote_detection(url, expected):
        """Only local paths and file:// are local; scp forms (user optional) are network."""
        assert gen_repo_info._is_local_remote(url) is expected


class TestNormalizeRepoUrl:
    """Tests for normalize_repo_url function."""

    @staticmethod
    def test_scp_style_ssh_url():
        """git@host:path.git should be normalized to https without .git."""
        assert (
            gen_repo_info.normalize_repo_url("git@gitcode.com:cann/runtime.git")
            == "https://gitcode.com/cann/runtime"
        )

    @staticmethod
    def test_ssh_scheme_url():
        """ssh://git@host/path.git should be normalized to https."""
        assert (
            gen_repo_info.normalize_repo_url("ssh://git@gitcode.com/cann/ge.git")
            == "https://gitcode.com/cann/ge"
        )

    @staticmethod
    def test_https_url_kept():
        """https url should only lose trailing .git and slash."""
        assert (
            gen_repo_info.normalize_repo_url("https://gitcode.com/cann/hixl.git/")
            == "https://gitcode.com/cann/hixl"
        )

    @staticmethod
    def test_ssh_url_with_port():
        """ssh port should be dropped instead of being merged into path."""
        assert (
            gen_repo_info.normalize_repo_url(
                "ssh://git@gitcode.com:29418/cann/runtime.git"
            )
            == "https://gitcode.com/cann/runtime"
        )

    @staticmethod
    @pytest.mark.parametrize(
        "url, expected",
        [
            (
                "https://oauth2:ghp_secret@gitcode.com/cann/runtime.git",
                "https://gitcode.com/cann/runtime",
            ),
            (
                "https://user:p@ss@gitcode.com/cann/runtime.git",
                "https://gitcode.com/cann/runtime",
            ),
            (
                "http://user:token@gitcode.com/cann/runtime.git",
                "http://gitcode.com/cann/runtime",
            ),
            (
                "https://user@gitcode.com/cann/runtime.git",
                "https://gitcode.com/cann/runtime",
            ),
        ],
    )
    def test_http_userinfo_stripped(url, expected):
        """Credentials/userinfo in http(s) url should be stripped."""
        result = gen_repo_info.normalize_repo_url(url)

        assert result == expected
        assert "@" not in result

    @staticmethod
    def test_http_url_with_port_kept():
        """http(s) port is not an ssh port and should be kept."""
        assert (
            gen_repo_info.normalize_repo_url(
                "https://oauth2:token@gitcode.com:8443/cann/runtime.git"
            )
            == "https://gitcode.com:8443/cann/runtime"
        )

    @staticmethod
    def test_path_at_sign_not_stripped():
        """@ after the first slash belongs to the path and must be kept."""
        assert (
            gen_repo_info.normalize_repo_url("https://gitcode.com/cann/runtime@x")
            == "https://gitcode.com/cann/runtime@x"
        )

    @staticmethod
    @pytest.mark.parametrize(
        "url",
        [
            "git@gitcode.com:cann/runtime.git",
            "ssh://git@gitcode.com:29418/cann/runtime.git",
            "https://oauth2:tok@gitcode.com/cann/runtime.git",
            "https://gitcode.com/cann/runtime",
        ],
    )
    def test_normalization_idempotent(url):
        """Normalization must be idempotent: normalize(normalize(x)) == normalize(x)."""
        once = gen_repo_info.normalize_repo_url(url)

        assert gen_repo_info.normalize_repo_url(once) == once


class TestDetectRepoInfo:
    """Tests for detect_repo_info function."""

    @staticmethod
    @requires_git
    def test_original_repo(tmp_path: Path):
        """Producer should yield normalized origin url and lowercase HEAD."""
        repo = tmp_path / "repo"
        repo.mkdir()
        head = _init_git_repo(
            repo,
            "DTS: normal commit\n",
            remote_url="git@gitcode.com:cann/runtime.git",
        )

        result = gen_repo_info.detect_repo_info(str(repo))

        assert result == ("https://gitcode.com/cann/runtime", head)

    @staticmethod
    @requires_git
    def test_subdir_repo_dir(tmp_path: Path):
        """Calling from a subdirectory should still locate the repository root."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "sub").mkdir()
        head = _init_git_repo(
            repo,
            "DTS: normal commit\n",
            remote_url="https://gitcode.com/cann/runtime.git",
        )

        result = gen_repo_info.detect_repo_info(str(repo / "sub"))

        assert result == ("https://gitcode.com/cann/runtime", head)

    @staticmethod
    @requires_git
    def test_credentialed_origin_stripped(tmp_path: Path):
        """Credentials in origin url should never reach the output."""
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(
            repo,
            "DTS: normal commit\n",
            remote_url="https://oauth2:ghp_secret@gitcode.com/cann/runtime.git",
        )

        url, _ = gen_repo_info.detect_repo_info(str(repo))

        assert url == "https://gitcode.com/cann/runtime"

    @staticmethod
    def test_uppercase_commit_lowercased(tmp_path: Path, monkeypatch):
        """Uppercase commit from git should be lowercased by the producer."""

        def fake_run_git(repo_dir, *args):
            if args == ("rev-parse", "--show-toplevel"):
                return f"{tmp_path}\n"
            if args == ("remote", "get-url", "origin"):
                return "git@gitcode.com:cann/runtime.git\n"
            if args == ("rev-parse", "HEAD"):
                return "A" * 40 + "\n"
            raise AssertionError(f"unexpected git call: {args}")

        monkeypatch.setattr(gen_repo_info, "_run_git", fake_run_git)

        url, commit_id = gen_repo_info.detect_repo_info(str(tmp_path))

        assert url == "https://gitcode.com/cann/runtime"
        assert commit_id == "a" * 40

    @staticmethod
    @requires_git
    def test_no_origin_raises(tmp_path: Path):
        """Repository without origin remote should raise RuntimeError."""
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo, "DTS: normal commit\n")

        with pytest.raises(RuntimeError):
            gen_repo_info.detect_repo_info(str(repo))

    @staticmethod
    @pytest.mark.parametrize(
        "remote_url",
        ["/home/build/machine/path/repo", "file:///home/build/machine/path/repo"],
    )
    @requires_git
    def test_local_origin_raises(tmp_path: Path, remote_url):
        """Local path / file:// origin must be treated as probe failure (empty state)."""
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo, "DTS: normal commit\n", remote_url=remote_url)

        with pytest.raises(RuntimeError, match="local remote"):
            gen_repo_info.detect_repo_info(str(repo))

    @staticmethod
    @requires_git
    def test_scp_like_origin_is_network(tmp_path: Path):
        """scp-like origin (with @) is a network remote and must not be treated local."""
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(
            repo, "DTS: normal commit\n", remote_url="user@host.example.com:cann/x.git"
        )

        url, _ = gen_repo_info.detect_repo_info(str(repo))

        # 非 git@ 的 scp 形态不做形态转换（仅去末尾 .git），按原样保留
        assert url == "user@host.example.com:cann/x"

    @staticmethod
    def test_non_git_dir_raises(tmp_path: Path):
        """Non git directory should raise RuntimeError."""
        with pytest.raises(RuntimeError):
            gen_repo_info.detect_repo_info(str(tmp_path))

    @staticmethod
    def test_non_sha1_commit_raises(tmp_path: Path, monkeypatch):
        """Commit ids not matching 40hex cannot fit the schema and count as failure."""

        def fake_run_git(repo_dir, *args):
            if args == ("rev-parse", "--show-toplevel"):
                return f"{tmp_path}\n"
            if args == ("remote", "get-url", "origin"):
                return "git@gitcode.com:cann/runtime.git\n"
            if args == ("rev-parse", "HEAD"):
                return "x" * 64 + "\n"
            raise AssertionError(f"unexpected git call: {args}")

        monkeypatch.setattr(gen_repo_info, "_run_git", fake_run_git)

        with pytest.raises(RuntimeError, match="invalid git info"):
            gen_repo_info.detect_repo_info(str(tmp_path))


class TestMain:
    """Tests for main function."""

    @staticmethod
    def _setup_main(monkeypatch, repo_dir, output_file, package_name="mypkg"):
        """Helper to set up argv for main."""
        monkeypatch.setattr(
            "sys.argv",
            [
                "gen_repo_info.py",
                "--package-name",
                package_name,
                "--repo-dir",
                str(repo_dir),
                "--output",
                str(output_file),
            ],
        )

    @staticmethod
    @requires_git
    def test_main_writes_entry(tmp_path: Path, monkeypatch):
        """main should write the package entry with normalized url and HEAD commit."""
        repo = tmp_path / "repo"
        repo.mkdir()
        head = _init_git_repo(
            repo,
            "DTS: normal commit\n",
            remote_url="git@gitcode.com:cann/runtime.git",
        )
        output_file = tmp_path / "out" / "repo_info.json"

        TestMain._setup_main(monkeypatch, repo, output_file)

        assert gen_repo_info.main() is True
        assert json.loads(output_file.read_text(encoding="utf-8")) == {
            "mypkg": {
                "repository_url": "https://gitcode.com/cann/runtime",
                "commit_id": head,
            }
        }

    @staticmethod
    @requires_git
    def test_main_no_origin_writes_empty(tmp_path: Path, monkeypatch, caplog):
        """Repository without origin should produce empty state {} with warning."""
        repo = tmp_path / "repo"
        repo.mkdir()
        _init_git_repo(repo, "DTS: normal commit\n")
        output_file = tmp_path / "repo_info.json"

        TestMain._setup_main(monkeypatch, repo, output_file)

        result = gen_repo_info.main()

        assert result is True
        assert output_file.exists()
        assert json.loads(output_file.read_text(encoding="utf-8")) == {}
        assert any("write empty info" in record.message for record in caplog.records)

    @staticmethod
    def test_main_non_git_writes_empty(tmp_path: Path, monkeypatch, caplog):
        """Non git directory should produce empty state {} with warning."""
        output_file = tmp_path / "repo_info.json"

        TestMain._setup_main(monkeypatch, tmp_path, output_file)

        result = gen_repo_info.main()

        assert result is True
        assert output_file.exists()
        assert json.loads(output_file.read_text(encoding="utf-8")) == {}
        assert any("write empty info" in record.message for record in caplog.records)

    @staticmethod
    def test_main_git_unavailable_writes_empty(tmp_path: Path, monkeypatch, caplog):
        """Unavailable git (OSError) should also fall into empty state, not crash."""

        def fake_run_git(repo_dir, *args):
            raise FileNotFoundError("git not found")

        monkeypatch.setattr(gen_repo_info, "_run_git", fake_run_git)
        output_file = tmp_path / "repo_info.json"

        TestMain._setup_main(monkeypatch, tmp_path, output_file)

        result = gen_repo_info.main()

        assert result is True
        assert output_file.exists()
        assert json.loads(output_file.read_text(encoding="utf-8")) == {}
        assert any("write empty info" in record.message for record in caplog.records)

    @staticmethod
    @requires_git
    def test_script_cli(tmp_path: Path):
        """Script should be runnable via CLI and produce the entry."""
        repo = tmp_path / "repo"
        repo.mkdir()
        head = _init_git_repo(
            repo,
            "DTS: normal commit\n",
            remote_url="https://gitcode.com/cann/runtime.git",
        )
        output_file = tmp_path / "repo_info.json"
        script_path = Path(gen_repo_info.__file__)

        result = subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--package-name",
                "mypkg",
                "--repo-dir",
                str(repo),
                "--output",
                str(output_file),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert json.loads(output_file.read_text(encoding="utf-8")) == {
            "mypkg": {
                "repository_url": "https://gitcode.com/cann/runtime",
                "commit_id": head,
            }
        }
