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

"""filelist模块测试。"""

from pathlib import Path

import pytest

from package import filelist
from package.filelist import (
    FileItem,
    generate_filelist,
    generate_record_file,
    parse_filelist,
    parse_records,
)


class DataSet:
    """数据集。"""

    class FileItem:
        share = FileItem(
            "metadef",
            "mkdir",
            "NA",
            "share",
            "TRUE",
            "750",
            "\\\\$username:\\\\$usergroup",
            "all",
            [],
            set(),
            "N",
            "FALSE",
            "NA",
            "metadef",
            [],
            set(),
            True,
        )

    filelist_1 = [FileItem.share]
    records_1 = ["share"]


def trans_filelist_to_parsed(filelist):
    return [fileitem._replace(is_dir=False) for fileitem in filelist]


def test_parse_filelist_1(tmp_path):
    path = tmp_path / "filelist_1.csv"
    generate_filelist(DataSet.filelist_1, str(path))
    result = list(parse_filelist(str(path)))
    expected = trans_filelist_to_parsed(DataSet.filelist_1)
    assert expected == result


def test_parse_records_1(tmp_path):
    path = tmp_path / "RECORD"
    generate_record_file(DataSet.records_1, str(path))
    result = list(parse_records(str(path)))
    assert DataSet.records_1 == result


def _make_sample_file_item(
    module="mod",
    operation="copy",
    rel_pkg="a.txt",
    rel_install="path/in/pkg",
    softlink=None,
    feature=None,
    is_common="N",
    pkg_inner_softlink=None,
    chip=None,
    is_dir=False,
):
    return filelist.create_file_item(
        module,
        operation,
        rel_pkg,
        rel_install,
        "N",
        "644",
        "root:root",
        "all",
        softlink or [],
        feature or set(),
        is_common,
        "FALSE",
        "",
        "block",
        pkg_inner_softlink or [],
        chip or set(),
        is_dir,
    )


def test_fileitem_to_string_and_header_and_soft_links_to_string():
    item = _make_sample_file_item(softlink=["link"], feature={"f1"})
    s = filelist.file_item_to_string(item)
    assert "mod,copy,a.txt,path/in/pkg" in s
    header = filelist.get_filelist_header_string()
    assert "module" in header and "chip" in header

    # soft_links_to_string 空/非空
    assert filelist.soft_links_to_string([]) == "NA"
    assert filelist.soft_links_to_string(["a", "b"]) == "a;b"


def test_create_file_item_type_validation():
    with pytest.raises(TypeError):
        filelist.create_file_item(
            "m",
            "copy",
            "a",
            "p",
            "N",
            "644",
            "root:root",
            "all",
            ["link"],
            ["not_set"],  # feature 需为 set
            "N",
            "FALSE",
            "",
            "block",
            [],
            set(),
            False,
        )


def test_is_relative_install_path_and_install_type_helpers():
    assert filelist.is_relative_install_path("a/b")
    assert not filelist.is_relative_install_path("/abs")

    class Dummy:
        def __init__(self, op, install_type):
            self.operation = op
            self.install_type = install_type

    fi = Dummy("copy", "all")
    assert filelist.is_specific_operations(fi, ["copy"])
    assert filelist.is_specific_install_type(fi, {"run"})


def test_fill_is_common_path_and_get_soft_links_not_in_common_paths():
    target_env = "arch-linux"
    f1 = _make_sample_file_item(
        rel_install=f"{target_env}/a",
        softlink=[f"{target_env}/b", "other/c"],
    )
    f2 = _make_sample_file_item(rel_install="other/d", softlink=[])
    fl = [f1, f2]

    out = list(filelist.fill_is_common_path(fl, target_env))
    assert out[0].is_common_path == "Y"
    # 第二个条目有软链指向公共目录，标记为 YY
    assert out[1].is_common_path in ("N", "YY")

    soft_links = list(filelist.get_soft_links_not_in_common_paths(fl, target_env))
    assert "other/c" in soft_links


def test_get_install_path_dirs_and_missing_dir_set_and_check_filelist():
    fi = _make_sample_file_item(
        operation="copy",
        rel_install="aaa/bbb/file.txt",
    )
    # 缺少中间目录，应该被检测到
    missing = filelist.get_missing_dir_set([fi])
    assert "aaa" in missing or "aaa/bbb" in missing

    # check_filelist 在有缺失目录时抛异常
    with pytest.raises(filelist.FilelistError):
        filelist.check_filelist([fi], check_features=False, check_move=False)


def test_print_helpers_and_move_safe_and_transform_funcs(tmp_path: Path):
    fi1 = _make_sample_file_item(
        operation="copy",
        rel_install="dir",
        rel_pkg="pkg/dir",
    )
    fi2 = _make_sample_file_item(
        operation="copy",
        rel_install="dir/sub/file",
        rel_pkg="pkg/dir/sub/file",
    )

    # print_missing_dir_set / print_unsafe_paths 主要验证可调用返回值
    mset = {"a", "b"}
    assert filelist.print_missing_dir_set(mset) == mset
    unsafe = ("x", "y")
    assert filelist.print_unsafe_paths(unsafe) == unsafe

    # check_move_safe 返回 tuple
    res = filelist.check_move_safe([fi1, fi2])
    assert isinstance(res, tuple)

    # is_nested_file_item 关系判断
    assert (
        filelist.is_nested_file_item(fi1, None) == filelist.FileItemRelation.NOT_NESTED
    )
    assert filelist.is_nested_file_item(fi1, fi1) == filelist.FileItemRelation.SAME
    assert filelist.is_nested_file_item(fi2, fi1) == filelist.FileItemRelation.NESTED

    # found_nested_file_item 抛异常
    with pytest.raises(filelist.FilelistError):
        filelist.found_nested_file_item(fi2, fi1)

    # convert_nested_path_in_filelist 将嵌套元素改为 del
    conv = list(filelist.convert_nested_path_in_filelist([fi1, fi2]))
    assert conv[0].operation == "copy"
    assert conv[1].operation == "del"

    # check_nested_path_in_filelist 只做检查和日志打印，不一定抛异常
    filelist.check_nested_path_in_filelist([fi1, fi2])

    # transform_nested_path_in_filelist 调用通过
    transformed = filelist.transform_nested_path_in_filelist([fi1, fi2])
    assert any(it.operation == "del" for it in transformed)

    # generate_filelist 输出文件
    out_dir = tmp_path
    out_file = out_dir / "filelist.csv"
    filelist.generate_filelist([fi1, fi2], str(out_file))
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "module,operation" in content.splitlines()[0]

    # get_transform_nested_path_func
    assert (
        filelist.get_transform_nested_path_func(True)
        is filelist.transform_nested_path_in_filelist
    )
    # Test identity function behavior instead of object identity
    identity_func = filelist.get_transform_nested_path_func(False)
    test_list = [fi1, fi2]
    assert identity_func(test_list) is test_list
