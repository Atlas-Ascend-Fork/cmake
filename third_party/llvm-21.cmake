# -----------------------------------------------------------------------------------------------------------
# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.
# -----------------------------------------------------------------------------------------------------------
include_guard(GLOBAL)

# 用法: init_cann_project() 后调用 add_cann_third_party(llvm-21)，再执行
# cmake --build <消费工程构建目录> --target third_party_llvm21: ExternalProject 在构建阶段
# 完成下载/校验/编译/安装，成功后方可用 LLVM21_INSTALL_PATH 消费（不自动 find_package)。

# LLVM 21 本身要求 CMake 3.20, 在下载源码之前就报告不兼容版本。
if(CMAKE_VERSION VERSION_LESS 3.20)
    message(FATAL_ERROR "[ThirdParty][llvm-21] CMake 3.20 or newer is required")
endif()

if(NOT CANN_3RD_LIB_PATH)
    message(FATAL_ERROR "[ThirdParty][llvm-21] CANN_3RD_LIB_PATH must be set")
endif()

# 仅支持宿主侧构建，不支持交叉编译。
if(CMAKE_CROSSCOMPILING)
    message(FATAL_ERROR "[ThirdParty][llvm-21] Host build only; cross compilation is not supported")
endif()

# ========== 基本路径配置 ==========
set(LLVM21_PROJECT_VERSION "21.1.8")
# 自定义源码包需同时设置 LLVM21_PROJECT_URL 和 LLVM21_PROJECT_SHA256。
set(LLVM21_PROJECT_URL
    "https://cann-3rd.obs.cn-north-4.myhuaweicloud.com/llvm/llvm-project-llvmorg-${LLVM21_PROJECT_VERSION}.src.tgz"
    CACHE STRING "LLVM 21 source archive URL or local path")
set(LLVM21_PROJECT_SHA256
    "4633a23617fa31a3ea51242586ea7fb1da7140e426bd62fc164261fe036aa142"
    CACHE STRING "LLVM 21 source archive SHA256")
set(LLVM21_SOURCE_PATH "${CANN_3RD_LIB_PATH}/llvm-21" CACHE PATH "LLVM 21 source directory")
# 离线包按 URL 的文件名在 pkg/ 下查找：自定义 URL/SHA256 时不会误用默认包导致哈希校验失败。
get_filename_component(_llvm21_archive_name "${LLVM21_PROJECT_URL}" NAME)
set(LLVM21_ARCHIVE "${CANN_3RD_LIB_PATH}/pkg/${_llvm21_archive_name}")

# 断言默认关闭，对齐 llvm.cmake 交付档位：开启会经 LLVM_DEFINITIONS 把 -D_DEBUG、
# -D_GLIBCXX_ASSERTIONS 传导给消费方，调试需要时显式置 ON。
option(LLVM21_ENABLE_ASSERTIONS "Enable LLVM 21 assertions" OFF)
# Python bindings 默认关闭：LLVM 21 依赖本仓未内置的 nanobind，干净环境默认路径会在
# LLVM 配置阶段失败；需要时显式开启（需预装 Python 开发包、pybind11 和 nanobind）。
option(LLVM21_ENABLE_PYTHON_BINDINGS "Enable MLIR Python bindings (requires Python development files, pybind11 and nanobind)" OFF)

# 并行编译作业数：默认留空=继承父构建并行度（见下方构建命令处的优先级说明），
# 显式设置为正整数则固定作业数。
set(LLVM21_BUILD_JOBS "" CACHE STRING "Maximum parallel LLVM 21 build jobs (empty = inherit from parent build)")
if(LLVM21_BUILD_JOBS AND NOT LLVM21_BUILD_JOBS MATCHES "^[1-9][0-9]*$")
    message(FATAL_ERROR "[ThirdParty][llvm-21] LLVM21_BUILD_JOBS must be a positive integer")
endif()

# ABI 沿用 CANN_CXX11_ABI, 未指定时默认为 0(旧 ABI)。
if(DEFINED CANN_CXX11_ABI)
    set(_llvm21_abi "${CANN_CXX11_ABI}")
else()
    set(_llvm21_abi 0)
endif()
if(NOT _llvm21_abi MATCHES "^[01]$")
    message(FATAL_ERROR "[ThirdParty][llvm-21] CANN_CXX11_ABI must be 0 or 1")
endif()

# ========== 工具链配置（探测宿主编译器与构建工具） ==========
# 编译器可用 LLVM21_C/CXX_COMPILER 显式指定，否则优先采用父工程的编译器。
if(NOT LLVM21_C_COMPILER AND CMAKE_C_COMPILER)
    set(LLVM21_C_COMPILER "${CMAKE_C_COMPILER}")
endif()
if(NOT LLVM21_CXX_COMPILER AND CMAKE_CXX_COMPILER)
    set(LLVM21_CXX_COMPILER "${CMAKE_CXX_COMPILER}")
endif()
find_program(LLVM21_C_COMPILER NAMES clang gcc cc DOC "LLVM 21 host C compiler")
find_program(LLVM21_CXX_COMPILER NAMES clang++ g++ c++ DOC "LLVM 21 host C++ compiler")
foreach(_llvm21_lang C CXX)
    if(NOT LLVM21_${_llvm21_lang}_COMPILER)
        message(FATAL_ERROR "[ThirdParty][llvm-21] Missing ${_llvm21_lang} compiler")
    endif()
    execute_process(COMMAND "${LLVM21_${_llvm21_lang}_COMPILER}" --version
        RESULT_VARIABLE _llvm21_result
        OUTPUT_VARIABLE _llvm21_${_llvm21_lang}_version
        ERROR_VARIABLE _llvm21_error)
    if(NOT _llvm21_result EQUAL 0)
        message(FATAL_ERROR "[ThirdParty][llvm-21] Compiler check failed: ${_llvm21_error}")
    endif()
endforeach()
find_program(_llvm21_ninja NAMES ninja ninja-build)
if(NOT _llvm21_ninja)
    message(FATAL_ERROR "[ThirdParty][llvm-21] Ninja is required")
endif()
# 使用 Python3_EXECUTABLE 选择 Python。
find_package(Python3 REQUIRED COMPONENTS Interpreter)

# ========== 编译选项 ==========
# Ninja + Release 构建静态组件库，启用 RTTI/EH, ccache launcher 由父工程透传；
# ABI 使用 project hook 注入, llvm-config --cxxflags 也会导出该定义。
# 安全加固与通用 flags 透传对齐 llvm.cmake/其他三方脚本约定。
# -fPIC 需在初始 flags 中显式给出：LLVM_ENABLE_PIC 要到 HandleLLVMOptions 才向
# CMAKE_<LANG>_FLAGS 追加 -fPIC，而此前 project() 的编译器检查与 config-ix 探测已按
# CMAKE_EXE_LINKER_FLAGS 中的 -pie 链接；在默认不生成 PIE 的工具链上，非 PIC 目标文件
# 会在这些检查中链接失败。LLVM 自身目标最终仍以其追加的 -fPIC 编译，产物不受影响。
set(_llvm21_common_flags "-fPIC -fstack-protector-strong -D_FORTIFY_SOURCE=2")
if(CANN_THIRD_PARTY_C_FLAGS)
    set(_llvm21_c_flags "${CANN_THIRD_PARTY_C_FLAGS} ${_llvm21_common_flags}")
else()
    set(_llvm21_c_flags "${_llvm21_common_flags}")
endif()
if(CANN_THIRD_PARTY_CXX_FLAGS)
    set(_llvm21_cxx_flags "${CANN_THIRD_PARTY_CXX_FLAGS} ${_llvm21_common_flags}")
else()
    set(_llvm21_cxx_flags "${_llvm21_common_flags}")
endif()
# 链接加固：RELRO/NOW/不可执行栈，可执行文件加 -pie。
set(_llvm21_exe_linker_flags "-Wl,-z,relro,-z,now,-z,noexecstack -pie")
set(_llvm21_shared_linker_flags "-Wl,-z,relro,-z,now,-z,noexecstack")
# compiler launcher（ccache 等）不影响产物，单独传递且不参与缓存签名，
# 避免是否启用 ccache 导致数小时的重复构建。
set(_llvm21_launcher_args
    -DCMAKE_C_COMPILER_LAUNCHER:STRING=${CMAKE_C_COMPILER_LAUNCHER}
    -DCMAKE_CXX_COMPILER_LAUNCHER:STRING=${CMAKE_CXX_COMPILER_LAUNCHER}
)
set(_llvm21_args
    -DCMAKE_BUILD_TYPE:STRING=Release
    -DCMAKE_INSTALL_LIBDIR:STRING=lib
    -DCMAKE_C_COMPILER:FILEPATH=${LLVM21_C_COMPILER}
    -DCMAKE_CXX_COMPILER:FILEPATH=${LLVM21_CXX_COMPILER}
    "-DCMAKE_C_FLAGS:STRING=${_llvm21_c_flags}"
    "-DCMAKE_CXX_FLAGS:STRING=${_llvm21_cxx_flags}"
    "-DCMAKE_EXE_LINKER_FLAGS:STRING=${_llvm21_exe_linker_flags}"
    "-DCMAKE_SHARED_LINKER_FLAGS:STRING=${_llvm21_shared_linker_flags}"
    "-DCMAKE_MODULE_LINKER_FLAGS:STRING=${_llvm21_shared_linker_flags}"
    -DPython3_EXECUTABLE:FILEPATH=${Python3_EXECUTABLE}
    -DPython_EXECUTABLE:FILEPATH=${Python3_EXECUTABLE}
    -DBUILD_SHARED_LIBS:BOOL=OFF
    -DLLVM_ENABLE_PROJECTS:STRING=mlir
    -DLLVM_TARGETS_TO_BUILD:STRING=host
    -DLLVM_ENABLE_ASSERTIONS:BOOL=${LLVM21_ENABLE_ASSERTIONS}
    -DLLVM_ENABLE_RTTI:BOOL=ON
    -DLLVM_ENABLE_EH:BOOL=ON
    -DLLVM_PARALLEL_LINK_JOBS:STRING=2
    -DLLVM_INSTALL_UTILS:BOOL=ON
    -DLLVM_BUILD_TOOLS:BOOL=ON
    -DLLVM_BUILD_UTILS:BOOL=ON
    -DLLVM_BUILD_EXAMPLES:BOOL=OFF
    -DLLVM_INCLUDE_EXAMPLES:BOOL=OFF
    -DLLVM_INCLUDE_BENCHMARKS:BOOL=OFF
    -DLLVM_ENABLE_BINDINGS:BOOL=OFF
    # 可选宿主依赖默认“找到即启用”，会写入导出的链接依赖且不参与缓存签名；
    # 统一关闭以保证产物与构建机环境无关（对齐 llvm.cmake 的 LLVM_ENABLE_ZSTD=OFF）。
    -DLLVM_ENABLE_LIBEDIT:BOOL=OFF
    -DLLVM_ENABLE_ZLIB:STRING=OFF
    -DLLVM_ENABLE_ZSTD:STRING=OFF
    -DLLVM_ENABLE_LIBXML2:STRING=OFF
    -DLLVM_INCLUDE_TESTS:BOOL=OFF
    -DMLIR_INCLUDE_TESTS:BOOL=OFF
    -DMLIR_INCLUDE_INTEGRATION_TESTS:BOOL=OFF
    -DMLIR_ENABLE_BINDINGS_PYTHON:BOOL=${LLVM21_ENABLE_PYTHON_BINDINGS}
)

# ========== 缓存签名与路径派生 ==========
# 长期保留 llvm-21/ 源码目录和 lib_cache/llvm_21.1.8/<签名>/ 安装结果, llvm-21-build/<签名>/
# 仅作临时工作目录, 成功后整体删除, 失败时保留现场。ABI、编译器、源码包摘要及关键选项参与
# 签名，缓存按签名隔离；并行数和 compiler launcher（ccache 等）不影响产物，不参与签名。
# 共享缓存勿跨 Docker/宿主机混用。
set(_llvm21_signature_input
    "schema=1;${LLVM21_PROJECT_VERSION};${LLVM21_PROJECT_SHA256};${LLVM21_SOURCE_PATH};${_llvm21_abi};${_llvm21_args};${_llvm21_C_version};${_llvm21_CXX_version};${Python3_VERSION};${CMAKE_HOST_SYSTEM_NAME};${CMAKE_HOST_SYSTEM_PROCESSOR}")
string(SHA256 _llvm21_signature "${_llvm21_signature_input}")
string(SUBSTRING "${_llvm21_signature}" 0 16 _llvm21_key)
set(LLVM21_INSTALL_PATH "${CANN_3RD_LIB_PATH}/lib_cache/llvm_${LLVM21_PROJECT_VERSION}/${_llvm21_key}")
set(LLVM21_BUILD_PATH "${CANN_3RD_LIB_PATH}/llvm-21-build/${_llvm21_key}")
set(LLVM21_CMAKE_DIR "${LLVM21_INSTALL_PATH}/lib/cmake/llvm")
set(MLIR21_CMAKE_DIR "${LLVM21_INSTALL_PATH}/lib/cmake/mlir")
set(_llvm21_manifest "${LLVM21_INSTALL_PATH}/.cann-llvm-21-signature")

# ========== 安装缓存检查 ==========
# 成功标记仅表示此前完成过安装，仍需检查必要工具、库和配置文件是否齐全；
# 此处不是对整个安装目录做内容校验。
set(_llvm21_artifacts
    bin/llvm-config bin/mlir-opt bin/mlir-tblgen bin/llvm-lit
    bin/lit/main.py
    include/llvm/IR/Module.h include/mlir/IR/MLIRContext.h
    lib/libLLVMCore.a lib/libMLIRIR.a lib/libMLIRSupport.a
    lib/cmake/llvm/LLVMConfig.cmake lib/cmake/mlir/MLIRConfig.cmake
)
if(LLVM21_ENABLE_PYTHON_BINDINGS)
    list(APPEND _llvm21_artifacts python_packages/mlir_core/mlir)
endif()
set(llvm21_FOUND FALSE)
if(EXISTS "${_llvm21_manifest}")
    file(READ "${_llvm21_manifest}" _llvm21_cached_signature)
    if(_llvm21_cached_signature STREQUAL _llvm21_signature)
        set(llvm21_FOUND TRUE)
        foreach(_llvm21_artifact IN LISTS _llvm21_artifacts)
            if(NOT EXISTS "${LLVM21_INSTALL_PATH}/${_llvm21_artifact}")
                set(llvm21_FOUND FALSE)
                break()
            endif()
        endforeach()
    endif()
endif()

if(llvm21_FOUND AND NOT FORCE_REBUILD_CANN_3RD)
    message(STATUS "[ThirdParty][llvm-21] use installed cache: ${LLVM21_INSTALL_PATH}")
    # 即使命中缓存也提供同名目标，供上层 add_dependencies 使用。
    add_custom_target(third_party_llvm21)
else()
    # ========== 构建路径配置 ==========
    # 控制文件和 stamp 与 LLVM 临时构建目录分离，成功后删除对象文件不会破坏
    # ExternalProject 自身的步骤状态；重新配置检测到安装不完整时清除旧 stamp。
    set(_llvm21_control "${CMAKE_BINARY_DIR}/llvm-21-external/${_llvm21_key}")
    file(REMOVE_RECURSE "${_llvm21_control}/stamp")
    file(REMOVE "${_llvm21_manifest}")
    if(FORCE_REBUILD_CANN_3RD)
        file(REMOVE_RECURSE "${LLVM21_BUILD_PATH}" "${LLVM21_INSTALL_PATH}")
    endif()
    file(MAKE_DIRECTORY "${_llvm21_control}")
    set(_llvm21_abi_hook "${_llvm21_control}/cann-llvm-21-abi.cmake")
    file(WRITE "${_llvm21_abi_hook}" "add_compile_definitions(_GLIBCXX_USE_CXX11_ABI=${_llvm21_abi})\n")

    # ========== 源码准备 ==========
    # 已有源码由调用者自行管理，修改后需开启 FORCE_REBUILD_CANN_3RD 触发重建。
    set(_llvm21_download_args)
    if(EXISTS "${LLVM21_SOURCE_PATH}/llvm/CMakeLists.txt")
        message(STATUS "[ThirdParty][llvm-21] Found local source code in ${LLVM21_SOURCE_PATH}")
        list(APPEND _llvm21_download_args DOWNLOAD_COMMAND "")
    else()
        # 源码目录已存在但不完整时必须为空，避免误向脏目录展开。
        if(EXISTS "${LLVM21_SOURCE_PATH}")
            file(GLOB _llvm21_entries "${LLVM21_SOURCE_PATH}/*" "${LLVM21_SOURCE_PATH}/.[!.]*" "${LLVM21_SOURCE_PATH}/..?*")
            if(NOT IS_DIRECTORY "${LLVM21_SOURCE_PATH}" OR _llvm21_entries)
                message(FATAL_ERROR "[ThirdParty][llvm-21] Incomplete source directory is not empty: ${LLVM21_SOURCE_PATH}")
            endif()
        endif()
        if(EXISTS "${LLVM21_ARCHIVE}")
            # local offline
            message(STATUS "[ThirdParty][llvm-21] Found local package in ${LLVM21_ARCHIVE}")
            set(REQ_URL "${LLVM21_ARCHIVE}")
        else()
            message(STATUS "[ThirdParty][llvm-21] Downloading LLVM 21.")
            set(REQ_URL "${LLVM21_PROJECT_URL}")
        endif()
        list(APPEND _llvm21_download_args
            URL ${REQ_URL}                              # 从本地 tgz 或远端获取源
            URL_HASH "SHA256=${LLVM21_PROJECT_SHA256}"  # 校验压缩包哈希正确性
            DOWNLOAD_DIR "${LLVM21_BUILD_PATH}/download"
            TIMEOUT 600
        )
    endif()

    # 成功标记仅在安装步骤完成后复制，失败时不留下可复用的完成标记。
    file(WRITE "${_llvm21_control}/signature" "${_llvm21_signature}")

    # ========== 构建命令 ==========
    set(LLVM21_CONFIGURE_COMMAND ${CMAKE_COMMAND}
        -S <SOURCE_DIR>/llvm -B <BINARY_DIR> -G Ninja
        -DCMAKE_MAKE_PROGRAM:FILEPATH=${_llvm21_ninja}
        -DCMAKE_INSTALL_PREFIX:PATH=${LLVM21_INSTALL_PATH}
        -DCMAKE_PROJECT_INCLUDE:FILEPATH=${_llvm21_abi_hook}
        ${_llvm21_args}
        ${_llvm21_launcher_args}
    )
    # 并行度优先级（LLVM21_BUILD_JOBS 留空时不传 --parallel）：
    # 1. make 父工程 -jN：MAKEFLAGS 携带作业池描述，支持 jobserver 的 ninja
    #    （Kitware 分发版）直接加入父进程作业池，受父进程并行数约束；
    # 2. CMAKE_BUILD_PARALLEL_LEVEL 环境变量（cmake --build 官方继承通道，
    #    注意：显式传不带数值的 --parallel 会屏蔽该变量，因此此处必须整体省略）；
    # 3. ninja 默认并行度（CPU 核数）。
    # 显式设置 LLVM21_BUILD_JOBS 则以固定数值调用 --parallel N。
    set(_llvm21_parallel_args)
    if(LLVM21_BUILD_JOBS)
        set(_llvm21_parallel_args "--parallel;${LLVM21_BUILD_JOBS}")
    endif()
    set(LLVM21_BUILD_COMMAND ${CMAKE_COMMAND} --build <BINARY_DIR> ${_llvm21_parallel_args})
    set(LLVM21_INSTALL_COMMAND ${CMAKE_COMMAND} --build <BINARY_DIR> --target install ${_llvm21_parallel_args})

    # ========== ExternalProject_Add ==========
    include(ExternalProject)
    cmake_policy(PUSH)
    if(POLICY CMP0135)
        cmake_policy(SET CMP0135 NEW)
    endif()
    ExternalProject_Add(third_party_llvm21
        ${_llvm21_download_args}
        PREFIX "${_llvm21_control}"              # 控制文件与 stamp 目录，和临时构建目录分离
        STAMP_DIR "${_llvm21_control}/stamp"
        TMP_DIR "${_llvm21_control}/tmp"
        SOURCE_DIR "${LLVM21_SOURCE_PATH}"       # 长期保留的源码目录
        BINARY_DIR "${LLVM21_BUILD_PATH}/build"  # 临时构建目录，安装成功后删除
        UPDATE_COMMAND ""
        CONFIGURE_COMMAND ${LLVM21_CONFIGURE_COMMAND}
        BUILD_COMMAND ${LLVM21_BUILD_COMMAND}
        INSTALL_COMMAND ${LLVM21_INSTALL_COMMAND}
        # 构建耗时较长，Ninja 父工程下实时输出日志而不是结束后一次性输出。
        USES_TERMINAL_CONFIGURE TRUE
        USES_TERMINAL_BUILD TRUE
        USES_TERMINAL_INSTALL TRUE
        EXCLUDE_FROM_ALL TRUE
    )
    cmake_policy(POP)

    # 安装成功后补装 lit 工具、落盘成功标记并清理临时构建目录。
    ExternalProject_Add_Step(third_party_llvm21 extra_install
        # 使用上游自带的启动脚本; lit 包放在同目录以便 Python 直接导入。
        COMMAND ${CMAKE_COMMAND} -E copy_directory <SOURCE_DIR>/llvm/utils/lit/lit ${LLVM21_INSTALL_PATH}/bin/lit
        COMMAND ${CMAKE_COMMAND} -E copy <SOURCE_DIR>/llvm/utils/lit/lit.py ${LLVM21_INSTALL_PATH}/bin/llvm-lit
        COMMAND ${CMAKE_COMMAND} -E copy "${_llvm21_control}/signature" "${_llvm21_manifest}"
        COMMAND ${CMAKE_COMMAND} -E remove_directory ${LLVM21_BUILD_PATH}
        DEPENDEES install
    )
endif()
