# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.
"""Exercise the real signing subprocess with a filesystem-only test client."""

import sys
from pathlib import Path

import pytest

import community_sign_build

CLIENT_SOURCE = """
import sys
from pathlib import Path

arguments = sys.argv[1:]
crl = Path(arguments[arguments.index('--crl') + 1])
if not crl.is_file():
    print('Test client cannot find CRL:', crl)
    sys.exit(2)
artifact = Path(arguments[arguments.index('--detached') + 1])
Path(str(artifact) + '.p7s').write_text('test-only signature placeholder')
"""


@pytest.fixture(name="signing_directory")
def make_signing_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    script_directory = tmp_path / "scripts"
    script_directory.mkdir()
    client = tmp_path / "test-sign-client"
    client.write_text(f"#!{sys.executable}\n{CLIENT_SOURCE}", encoding="utf-8")
    client.chmod(0o700)
    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"test payload")
    monkeypatch.setattr(community_sign_build, "SCRIPT_DIR", str(script_directory))
    monkeypatch.setattr(community_sign_build, "SIGN_CLIENT_PATH", str(client))
    return artifact


@pytest.mark.parametrize("relative", [True, False])
def test_local_crl_works_from_a_different_signer_directory(
    signing_directory, monkeypatch, relative
):
    crl = Path("crls/local.crl")
    crl.parent.mkdir()
    crl.write_bytes(b"test-only CRL placeholder")
    monkeypatch.setenv("CRL_FILE_PATH", str(crl if relative else crl.resolve()))
    assert community_sign_build.main(["sign", str(signing_directory)]) is True
    assert signing_directory.with_suffix(".bin.p7s").is_file()


def test_downloaded_crl_works_with_a_relative_output_directory(
    signing_directory, monkeypatch
):
    monkeypatch.delenv("CRL_FILE_PATH", raising=False)

    def download_once(_command, crl_path, _attempt):
        Path(crl_path).write_bytes(b"test-only CRL placeholder")
        return True

    monkeypatch.setattr(community_sign_build, "_download_crl_once", download_once)
    assert (
        community_sign_build.main(["sign", "--crl-dir", "crls", str(signing_directory)])
        is True
    )
    assert signing_directory.with_suffix(".bin.p7s").is_file()
