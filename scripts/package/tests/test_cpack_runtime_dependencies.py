# -----------------------------------------------------------------------------------------------------------
# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.
# -----------------------------------------------------------------------------------------------------------

"""验证跨目录的 CPack 运行依赖及实际 DEB 元数据。"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

_FRAMEWORK = Path(__file__).resolve().parents[3] / "function" / "prepare.cmake"
_ORDERS = [("metadef", "npu-runtime"), ("npu-runtime", "metadef")]


@pytest.fixture
def cmake():
    """配置测试需要实际的 CMake。"""
    executable = shutil.which("cmake")
    if executable is None:
        pytest.skip("未安装 CMake")
    return executable


def _configure(cmake, tmp_path, packages, order):
    source = tmp_path / "source"
    source.mkdir()
    root = [
        "cmake_minimum_required(VERSION 3.20)",
        "project(cpack_runtime_dependencies NONE)",
        f'include("{_FRAMEWORK.as_posix()}")',
        "set(ENABLE_UNIFIED_BUILD TRUE)",
        "set(CANN_PACKAGES metadef npu-runtime ge-compiler)",
        # 测试 DEB/RPM 依赖配置，不下载无关的 makeself 工具。
        "function(add_cann_third_party name)",
        '  if(NOT name STREQUAL "makeself-fetch")',
        '    message(FATAL_ERROR "Unexpected third-party dependency: ${name}")',
        "  endif()",
        "endfunction()",
    ]
    root.extend(f"add_subdirectory({name})" for name in order)
    (source / "CMakeLists.txt").write_text("\n".join(root) + "\n", encoding="utf-8")
    for name, content in packages.items():
        directory = source / name
        directory.mkdir()
        (directory / "CMakeLists.txt").write_text(content, encoding="utf-8")
    build = tmp_path / "build"
    subprocess.run(
        [cmake, "-S", str(source), "-B", str(build)],
        capture_output=True,
        text=True,
        check=True,
    )
    return build


def _package(component, dependencies=""):
    return f"""set_cann_package({component} VERSION "9.2.0")
{dependencies}
file(WRITE "${{CMAKE_CURRENT_BINARY_DIR}}/{component}.txt" "{component}\n")
install(FILES "${{CMAKE_CURRENT_BINARY_DIR}}/{component}.txt"
    DESTINATION share/{component} COMPONENT {component})
set_cann_cpack_config({component} PACKAGE_TYPE "deb,rpm")
"""


def _dependency_fields(build, component):
    config = (build / "CPackConfig.cmake").read_text(encoding="utf-8")
    prefix = component.upper()
    result = []
    for name in [
        f"CPACK_DEBIAN_{prefix}_PACKAGE_DEPENDS",
        f"CPACK_RPM_{prefix}_PACKAGE_REQUIRES",
    ]:
        match = re.search(rf'^set\({re.escape(name)} "(.*)"\)$', config, re.MULTILINE)
        assert match is not None, name
        result.append(match.group(1))
    return tuple(result)


def _sibling_packages():
    return {
        "metadef": _package(
            "metadef", 'set_cann_run_dependencies(runtime "CUR_MAJOR_MINOR_VER")'
        ),
        "npu-runtime": _package("npu-runtime"),
    }


@pytest.mark.parametrize("order", _ORDERS)
def test_sibling_package_dependencies(cmake, tmp_path, order):
    """目录配置顺序不影响已声明依赖，也不污染无依赖组件。"""
    build = _configure(cmake, tmp_path, _sibling_packages(), order)
    config = (build / "CPackConfig.cmake").read_text(encoding="utf-8")
    assert 'set(CPACK_PACKAGE_VERSION "9.2.0")' in config
    assert _dependency_fields(build, "metadef") == (
        "npu-runtime (>= 9.2)",
        "npu-runtime >= 9.2",
    )
    assert _dependency_fields(build, "npu-runtime") == ("", "")


@pytest.mark.parametrize("order", _ORDERS)
def test_deb_control_dependencies(cmake, tmp_path, order):
    """实际 DEB 包的 Depends 字段保留跨目录运行依赖。"""
    cpack = shutil.which("cpack")
    dpkg_deb = shutil.which("dpkg-deb")
    if cpack is None or dpkg_deb is None:
        pytest.skip("实际 DEB 测试需要 cpack 和 dpkg-deb")
    build = _configure(cmake, tmp_path, _sibling_packages(), order)
    # 使用生成的依赖配置；最小载荷不需要 CANN 安装脚本或打包前后处理。
    wrapper = build / "dependency-test.cmake"
    wrapper.write_text(
        f'include("{(build / "CPackConfig.cmake").as_posix()}")\n'
        'set(CPACK_PRE_BUILD_SCRIPTS "")\n'
        'set(CPACK_POST_BUILD_SCRIPTS "")\n'
        'set(CPACK_DEBIAN_PACKAGE_CONTROL_EXTRA "")\n',
        encoding="utf-8",
    )
    subprocess.run(
        [cpack, "--config", str(wrapper), "-G", "DEB"],
        cwd=build,
        capture_output=True,
        text=True,
        check=True,
    )
    packages = list(build.glob("*.deb"))
    assert len(packages) == 2
    metadata = {}
    for package in packages:
        name = subprocess.check_output(
            [dpkg_deb, "--field", str(package), "Package"], text=True
        ).strip()
        metadata[name] = tuple(
            subprocess.check_output(
                [dpkg_deb, "--field", str(package), field], text=True
            ).strip()
            for field in ("Depends", "Version")
        )
    assert metadata == {
        "metadef": ("npu-runtime (>= 9.2)", "9.2.0"),
        "npu-runtime": ("", "9.2.0"),
    }


def test_components_in_one_directory(cmake, tmp_path):
    """同仓多组件的依赖在兄弟目录重新生成配置后仍相互隔离。"""
    packages = {
        "ge": _package(
            "metadef", 'set_cann_run_dependencies(runtime "CUR_MAJOR_MINOR_VER")'
        )
        + _package("ge-compiler", 'set_cann_run_dependencies(metadef ">=9.1")'),
        "runtime": _package("npu-runtime"),
    }
    build = _configure(cmake, tmp_path, packages, ["ge", "runtime"])
    assert _dependency_fields(build, "metadef") == (
        "npu-runtime (>= 9.2)",
        "npu-runtime >= 9.2",
    )
    assert _dependency_fields(build, "ge-compiler") == (
        "metadef (>= 9.1)",
        "metadef >= 9.1",
    )
    assert _dependency_fields(build, "npu-runtime") == ("", "")


def test_repeated_configuration_updates_dependencies(cmake, tmp_path):
    """同一组件再次配置时使用最新依赖，并保持依赖去重。"""
    packages = {
        "metadef": _package(
            "metadef", 'set_cann_run_dependencies(runtime "CUR_MAJOR_MINOR_VER")'
        )
        + 'set_cann_run_dependencies(runtime "CUR_MAJOR_MINOR_VER")\n'
        + 'set_cann_run_dependencies(asc_devkit ">=9.1")\n'
        + 'set_cann_cpack_config(metadef PACKAGE_TYPE "deb,rpm")\n',
        "runtime": _package("npu-runtime"),
    }
    build = _configure(cmake, tmp_path, packages, ["metadef", "runtime"])
    assert _dependency_fields(build, "metadef") == (
        "npu-runtime (>= 9.2), asc-devkit (>= 9.1)",
        "npu-runtime >= 9.2, asc-devkit >= 9.1",
    )


def test_redeclared_package_clears_dependencies(cmake, tmp_path):
    """包重新声明为空依赖时，不沿用上一次配置的运行依赖。"""
    packages = {
        "metadef": _package(
            "metadef", 'set_cann_run_dependencies(runtime "CUR_MAJOR_MINOR_VER")'
        )
        + 'set_cann_package(metadef VERSION "9.2.0")\n'
        + 'set_cann_cpack_config(metadef PACKAGE_TYPE "deb,rpm")\n',
        "runtime": _package("npu-runtime"),
    }
    build = _configure(cmake, tmp_path, packages, ["metadef", "runtime"])
    assert _dependency_fields(build, "metadef") == ("", "")
