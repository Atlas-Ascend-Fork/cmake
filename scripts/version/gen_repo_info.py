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

"""默认仓库信息生产者：从组件仓 git 探测仓库信息并写入仓库信息 JSON。

探测失败（非 git 仓库、无 origin、git 不可用、源码 tarball 等）是合法空态：
写 {} 并以 0 退出，消费者将省略 repository_url / commit_id 两字段。
值处理在本脚本完成：URL 归一化（ssh/scp 转 https、丢弃 ssh 端口、剥离 http(s)
userinfo 凭据、去末尾 .git）与 commit_id 统一小写；消费者只做 schema 校验并直接消费。
"""

import argparse
import json
import logging
import os
import re
import subprocess
from typing import Dict, Tuple

REPOSITORY_URL_FIELD = "repository_url"
COMMIT_ID_FIELD = "commit_id"
_COMMIT_ID_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")
_SSH_URL_PATTERN = re.compile(r"^ssh://git@([^/:]+)(?::\d+)?/(.+)$")
_SCP_URL_PATTERN = re.compile(r"^git@([^/:]+):(.+)$")
_HTTP_USERINFO_PATTERN = re.compile(r"^(https?://)(?:[^/@]*@)+", re.IGNORECASE)


def _run_git(repo_dir: str, *args: str) -> str:
    """在指定目录执行 git 命令，失败时抛出 RuntimeError；解码容错保证不因异常字节崩溃。"""
    result = subprocess.run(
        ["git", "-C", repo_dir, *args],
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout


def _is_local_remote(url: str) -> bool:
    """判定 origin 是否为本地形态（本地路径或 file://），此类地址会把构建机路径带入制品。"""
    if url.startswith("file://"):
        return True
    if "://" in url:
        return False
    # 无 scheme 时按 scp 语法（[user@]host:path，user 可省略）判定：
    # 冒号出现在首个斜杠之前视为网络远端；无冒号的按本地路径处理
    return ":" not in url.split("/", 1)[0]


def normalize_repo_url(url: str) -> str:
    """将 git 远端地址归一化为 https 形式并去掉末尾 .git（幂等）。"""
    url = url.strip().rstrip("/")
    ssh_match = _SSH_URL_PATTERN.match(url)
    scp_match = _SCP_URL_PATTERN.match(url)
    if ssh_match:
        # ssh://git@host[:port]/path：端口是 ssh 端口，归一化为 https 时丢弃
        url = f"https://{ssh_match.group(1)}/{ssh_match.group(2)}"
    elif scp_match:
        url = f"https://{scp_match.group(1)}/{scp_match.group(2)}"
    else:
        # https://<user>:<token>@host/path：剥离 userinfo（含密码含 @ 的多段形态），
        # 避免凭据写入 version.info
        url = _HTTP_USERINFO_PATTERN.sub(r"\1", url, count=1)
    if url.endswith(".git"):
        url = url[: -len(".git")]
    return url.rstrip("/")


def detect_repo_info(repo_dir: str) -> Tuple[str, str]:
    """从组件仓 git 探测（归一化 URL, 小写提交号）；探测失败时抛出 RuntimeError。"""
    repo_root = _run_git(repo_dir, "rev-parse", "--show-toplevel").strip()
    url = _run_git(repo_root, "remote", "get-url", "origin").strip()
    commit_id = _run_git(repo_root, "rev-parse", "HEAD").strip()
    if not url or not _COMMIT_ID_PATTERN.match(commit_id):
        # 40hex 之外的形态（如 sha256 对象格式）无法写入契约 schema，按采集失败处理
        raise RuntimeError(
            f"invalid git info of {repo_root} (url={url!r}, commit_id={commit_id!r})"
        )
    if _is_local_remote(url):
        # 本地路径/file:// 形态的 origin 无追溯价值且会泄露构建机路径，按采集失败处理
        raise RuntimeError(f"origin of {repo_root} is a local remote: {url!r}")
    return normalize_repo_url(url), commit_id.lower()


def dump_repo_info(output: str, repo_info: Dict[str, Dict[str, str]]) -> None:
    """写仓库信息 JSON 产物（必须创建产物文件，构建系统依赖其存在）。"""
    output_dir = os.path.dirname(output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(output, "w", encoding="utf-8") as file:
        json.dump(repo_info, file, indent=4)
        file.write("\n")


def main():
    """主流程。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-name", required=True, help="Package name.")
    parser.add_argument(
        "--repo-dir", required=True, help="Component repository directory."
    )
    parser.add_argument("--output", required=True, help="Output JSON file path.")
    args = parser.parse_args()

    logging.basicConfig(
        format=f"{os.path.basename(__file__)}: %(levelname)s: %(message)s"
    )

    try:
        url, commit_id = detect_repo_info(args.repo_dir)
    except (OSError, RuntimeError) as error:
        # 采集不到是合法空态：写 {}，构建继续（消费者省略两字段）
        logging.warning(
            "Cannot detect repo info of %s for package %s, write empty info: %s",
            args.repo_dir,
            args.package_name,
            error,
        )
        dump_repo_info(args.output, {})
        return True

    dump_repo_info(
        args.output,
        {
            args.package_name: {
                REPOSITORY_URL_FIELD: url,
                COMMIT_ID_FIELD: commit_id,
            }
        },
    )
    return True


if __name__ == "__main__":
    main()
