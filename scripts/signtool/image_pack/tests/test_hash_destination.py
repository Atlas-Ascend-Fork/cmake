# -----------------------------------------------------------------------------------------------------------
# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.
# -----------------------------------------------------------------------------------------------------------
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest

spec = importlib.util.spec_from_file_location(
    "ini_gen", Path(__file__).parents[1] / "ini_gen.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize("kind", ["sibling", "symlink", "parent"])
def test_reject_outside_xml_directory(tmp_path, monkeypatch, kind):
    base = tmp_path / "base"
    base.mkdir()
    outside = tmp_path / "base-extra"
    outside.mkdir()
    link = base / "link"
    link.symlink_to(outside, target_is_directory=True)
    xml = base / "images.xml"
    xml.write_text("<image_info/>")
    target = {"sibling": outside, "symlink": link, "parent": base / ".."}[kind]
    monkeypatch.setattr(
        module,
        "get_args",
        lambda: SimpleNamespace(
            inFilePath=str(xml), hash_list=True, hash_list_path=str(target)
        ),
    )
    with pytest.raises(ValueError):
        module.gen_ini()
    assert not (outside / "hash-list.img").exists()


def test_accept_child_and_base(tmp_path, monkeypatch):
    image = tmp_path / "image"
    image.write_bytes(b"payload")
    xml = tmp_path / "images.xml"
    xml.write_text(f'<image_info><image tag="data" path="{image}"/></image_info>')
    for target in (tmp_path, tmp_path / "child"):
        target.mkdir(exist_ok=True)
        monkeypatch.setattr(
            module,
            "get_args",
            lambda: SimpleNamespace(
                inFilePath=str(xml), hash_list=True, hash_list_path=str(target)
            ),
        )
        assert module.gen_ini() == 0
        assert (target / "hash-list.img").read_text().startswith("data,")
