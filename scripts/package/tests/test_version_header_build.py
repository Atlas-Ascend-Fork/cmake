# -----------------------------------------------------------------------------------------------------------
# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.
# -----------------------------------------------------------------------------------------------------------

"""The version header must follow updates to its generator script."""

import shutil
import subprocess
import time
from pathlib import Path


def test_generator_change_rebuilds_version_header(tmp_path):
    repository = Path(__file__).resolve().parents[3]
    framework = tmp_path / "cann-cmake"
    (framework / "function").mkdir(parents=True)
    (framework / "scripts/package").mkdir(parents=True)
    shutil.copy2(
        repository / "function/prepare.cmake", framework / "function/prepare.cmake"
    )
    generator = framework / "scripts/package/generate_version_header.sh"
    shutil.copy2(repository / "scripts/package/generate_version_header.sh", generator)
    source = tmp_path / "consumer"
    source.mkdir()
    (source / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.16)\n"
        "project(version_header NONE)\n"
        f'include("{framework}/function/prepare.cmake")\n'
        "set(PRODUCT_SIDE device)\n"
        "gen_cann_version_header(sample VERSION 9.0.0)\n",
        encoding="utf-8",
    )
    build = tmp_path / "build"
    subprocess.run(
        ["cmake", "-S", str(source), "-B", str(build), "-G", "Unix Makefiles"],
        check=True,
    )
    command = ["cmake", "--build", str(build), "--target", "gen_sample_version_header"]
    subprocess.run(command, check=True)
    header = build / "include/version/sample_version.h"
    assert '#define SAMPLE_VERSION_STR "9.0.0"' in header.read_text(encoding="utf-8")

    time.sleep(1)
    generator.write_text(
        generator.read_text(encoding="utf-8").replace(
            'echo "#define ${package_name}_PATCH ${release_part[2]}"',
            'echo "#define ${package_name}_PATCH ${release_part[2]}"\n'
            '    echo "#define ${package_name}_GENERATOR_REV 2"',
        ),
        encoding="utf-8",
    )
    subprocess.run(command, check=True)

    assert "#define SAMPLE_GENERATOR_REV 2" in header.read_text(encoding="utf-8")
