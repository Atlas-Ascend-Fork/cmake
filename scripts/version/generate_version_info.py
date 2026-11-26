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

"""生成version.info文件（消费者：读仓库信息 JSON，只做 schema 校验并直接消费）。"""

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from functools import partial
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

REPOSITORY_URL_FIELD = "repository_url"
COMMIT_ID_FIELD = "commit_id"
REPO_INFO_FIELDS = (REPOSITORY_URL_FIELD, COMMIT_ID_FIELD)

_COMMIT_ID_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")
_PKG_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
_EXTRA_FIELD_PATTERN = re.compile(r"^([A-Za-z0-9_.-]+)=([^\n\r]+)$")
_RESERVED_EXTRA_FIELD_KEYS = frozenset(
    {"version", "version_dir", "timestamp", "repository_url", "commit_id"}
)
_RESERVED_EXTRA_FIELD_PREFIX = "required_package_"


def normalize_extra_fields(fields: Iterable[str]) -> List[str]:
    """校验附加字段，要求形如 key=value 且不含换行。"""
    normalized = []
    for field in fields:
        line = field.strip()
        match = _EXTRA_FIELD_PATTERN.match(line)
        if not match:
            raise ValueError(
                f"Invalid extra field {field!r}, expect <key>=<value> without newline"
            )
        key = match.group(1)
        lower_key = key.lower()
        if lower_key in _RESERVED_EXTRA_FIELD_KEYS or lower_key.startswith(
            _RESERVED_EXTRA_FIELD_PREFIX
        ):
            raise ValueError(f"Reserved extra field key {key!r} is not allowed")
        normalized.append(line)
    return normalized


def _reject_duplicate_keys(
    pairs: Iterable[Tuple[str, object]], path: str = ""
) -> Dict[str, object]:
    """object_pairs_hook：JSON 对象出现重复键即报错（json.load 默认静默取后者）。"""
    obj: Dict[str, object] = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"Duplicate JSON key {key!r} in {path}")
        obj[key] = value
    return obj


def load_repo_info_file(path: str) -> Dict[str, Dict[str, str]]:
    """解析并校验仓库信息 JSON，返回 {包名: {字段: 值}}。

    条目要么完整（两字段齐备且合法）、要么缺失（无该包条目），不写 null/占位。
    """
    with open(path, encoding="utf-8") as file:
        repo_info = json.load(
            file, object_pairs_hook=partial(_reject_duplicate_keys, path=path)
        )
    if not isinstance(repo_info, dict):
        raise ValueError(f"Repo info file {path} must contain a JSON object")
    for pkg_name, pkg_info in repo_info.items():
        if not _PKG_NAME_PATTERN.match(pkg_name):
            raise ValueError(f"Invalid package name {pkg_name!r} in {path}")
        if not isinstance(pkg_info, dict):
            raise ValueError(
                f"Entry of package {pkg_name!r} in {path} must be a JSON object"
            )
        unknown_fields = [field for field in pkg_info if field not in REPO_INFO_FIELDS]
        if unknown_fields:
            raise ValueError(
                f"Unknown field(s) {unknown_fields} for package {pkg_name!r} in {path}, "
                f"only {REPOSITORY_URL_FIELD} / {COMMIT_ID_FIELD} are allowed"
            )
        missing_fields = [field for field in REPO_INFO_FIELDS if field not in pkg_info]
        if missing_fields:
            raise ValueError(
                f"Package {pkg_name!r} in {path} must define both "
                f"{REPOSITORY_URL_FIELD} and {COMMIT_ID_FIELD}, "
                f"missing: {', '.join(missing_fields)}"
            )
        for field in REPO_INFO_FIELDS:
            value = pkg_info[field]
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Empty {field} for package {pkg_name!r} in {path}")
            if "\n" in value or "\r" in value:
                # 与 EXTRA_FIELDS 的换行防护一致，拒绝向 version.info 注入额外行
                raise ValueError(
                    f"Invalid {field} for package {pkg_name!r} in {path}, "
                    "newline is not allowed"
                )
            if field == COMMIT_ID_FIELD and not _COMMIT_ID_PATTERN.match(value):
                raise ValueError(
                    f"Invalid commit_id {value!r} for package {pkg_name!r} in {path}, "
                    "expect 40 hex characters"
                )
    return repo_info


def resolve_repo_info(
    pkg_name: Optional[str],
    repo_info_file: Optional[str],
) -> Tuple[Optional[str], Optional[str]]:
    """查本包条目：存在原样返回（值处理在生产者完成）；缺失告警并省略两字段。"""
    if not pkg_name or not repo_info_file:
        return None, None
    pkg_info = load_repo_info_file(repo_info_file).get(pkg_name)
    if pkg_info is None:
        logging.warning(
            "Package %r not found in %s, skip repository_url/commit_id",
            pkg_name,
            repo_info_file,
        )
        return None, None
    return (
        pkg_info[REPOSITORY_URL_FIELD],
        pkg_info[COMMIT_ID_FIELD],
    )


def gen_version_info_content(
    version: str,
    deps: Iterable[str],
    repository_url: Optional[str] = None,
    commit_id: Optional[str] = None,
    extra_fields: Optional[Iterable[str]] = None,
) -> Iterator[str]:
    """生成version.info文件内容。"""
    extra_fields = normalize_extra_fields(extra_fields or ())
    yield f"Version={version}"
    yield "version_dir=cann"
    deps_iter = iter(deps)
    for dep_pkg in deps_iter:
        dep_info = next(deps_iter)
        yield f'required_package_{dep_pkg}_version="{dep_info}"'
    if repository_url is not None or commit_id is not None:
        if not repository_url or not commit_id:
            raise ValueError("repository_url and commit_id must be provided together.")
        yield f"{REPOSITORY_URL_FIELD}={repository_url}"
        yield f"{COMMIT_ID_FIELD}={commit_id}"
    if os.environ.get("tagInfo"):
        tag_info = os.environ.get("tagInfo")
        timestamp = "_".join(tag_info.split("_")[-3:-1])
    else:
        timestamp = datetime.now(timezone(timedelta(hours=8))).strftime(
            "%Y%m%d_%H%M%S%f"
        )[:-3]
    yield f"timestamp={timestamp}"
    yield from extra_fields
    yield ""  # for last \n


def main():
    """主流程。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("version", help="Version number.")
    parser.add_argument("deps", nargs="*", help="Dependency informations.")
    parser.add_argument("--output", required=True, help="Output file path.")
    parser.add_argument(
        "--package-name",
        help="Package name used to look up repository info.",
    )
    parser.add_argument(
        "--repo-info-file",
        help="Repo info JSON with <pkg> repository_url / commit_id.",
    )
    parser.add_argument(
        "--extra-field",
        action="append",
        default=[],
        help="Additional <key>=<value> line appended after timestamp; repeatable.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        format=f"{os.path.basename(__file__)}: %(levelname)s: %(message)s"
    )

    if len(args.deps) % 2 != 0:
        logging.error("The deps argument must contain an even number of elements!")
        return False

    try:
        repository_url, commit_id = resolve_repo_info(
            args.package_name, args.repo_info_file
        )
        content = "\n".join(
            gen_version_info_content(
                args.version,
                args.deps,
                repository_url,
                commit_id,
                args.extra_field,
            )
        )
    except json.JSONDecodeError as error:
        logging.error(
            "Invalid JSON in repo info file %s: %s", args.repo_info_file, error
        )
        return False
    except (OSError, ValueError) as error:
        logging.error("%s", error)
        return False

    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as file:
        file.write(content)

    return True


if __name__ == "__main__":
    if not main():
        sys.exit(1)
