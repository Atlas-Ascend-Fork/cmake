# ------------------------------------------------------------------------------
# Unified LLVM Source Cache Module
# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.
# ------------------------------------------------------------------------------
include_guard(GLOBAL)

function(__cann_build_llvm)
    if(EXISTS ${CANN_LLVM_SOURCE_PATH}/llvm/CMakeLists.txt)
        message(STATUS "[ThirdParty][llvm] LLVM source found in ${CANN_LLVM_SOURCE_PATH}, and not force rebuild")
        set(REQ_URL "")
    elseif(EXISTS ${CANN_LLVM_ARCHIVE})
        set(REQ_URL ${CANN_LLVM_ARCHIVE})
    else()
        message(STATUS "[ThirdParty][llvm] Downloading LLVM from ${CANN_LLVM_URL}")
        set(REQ_URL ${CANN_LLVM_URL})
    endif()
    include(ExternalProject)
    # feature-vpto patch: upstream LLVM 19.1.7 -> vpto fork (SimtEntry, float8).
    # The vpto calling conventions are required by PTOAS. Environments that ship a
    # pre-patched LLVM source (e.g. the "yellow zone" CI, which pre-patches the
    # source and cannot reach the patch release asset) are detected by the
    # SimtEntry marker in CallingConv.h and skip the patch entirely, including the
    # download. When the source still needs the patch, reuse a cached copy first
    # and fall back to downloading; a failed download is tolerated (the source may
    # be pre-patched, or the later PTOAS build will fail with a missing SimtEntry).
    set(LLVM_SOURCE_HAS_VPTO FALSE)
    set(LLVM_SOURCE_VPTO_MARKER "${CANN_LLVM_SOURCE_PATH}/llvm/include/llvm/IR/CallingConv.h")
    if(EXISTS "${LLVM_SOURCE_VPTO_MARKER}")
        file(STRINGS "${LLVM_SOURCE_VPTO_MARKER}" LLVM_SOURCE_VPTO_SIMT_LINE REGEX "SimtEntry")
        if(LLVM_SOURCE_VPTO_SIMT_LINE)
            set(LLVM_SOURCE_HAS_VPTO TRUE)
        endif()
    endif()

    set(LLVM_VPTO_PATCH_FILE "")
    set(LLVM_VPTO_PATCH_READY FALSE)
    if(NOT LLVM_SOURCE_HAS_VPTO)
        foreach(_vpto_cand
                ${CANN_3RD_LIB_PATH}/feature-vpto-last3.patch
                ${CANN_LLVM_PATCH_PATH}/feature-vpto-last3.patch)
            if(EXISTS ${_vpto_cand})
                set(LLVM_VPTO_PATCH_FILE ${_vpto_cand})
                set(LLVM_VPTO_PATCH_READY TRUE)
                message(STATUS "[ThirdParty][llvm] vpto patch use cache: ${LLVM_VPTO_PATCH_FILE}")
                break()
            endif()
        endforeach()
        if(NOT LLVM_VPTO_PATCH_READY)
            message(STATUS "[ThirdParty][llvm] vpto patch not cached, downloading to: ${CANN_LLVM_PATCH_PATH}/feature-vpto-last3.patch")
            file(MAKE_DIRECTORY ${CANN_LLVM_PATCH_PATH})
            # file(DOWNLOAD ... EXPECTED_HASH) hard-fails on any failed download
            # (the empty/partial target fails the hash check even with STATUS set),
            # which would abort the configure in sandboxed environments. Download
            # without a hash and verify afterwards.
            file(REMOVE "${CANN_LLVM_PATCH_PATH}/feature-vpto-last3.patch")
            file(DOWNLOAD
                "https://gitcode.com/cann-src-third-party/llvm/releases/download/19.1.7-h0/feature-vpto-last3.patch"
                "${CANN_LLVM_PATCH_PATH}/feature-vpto-last3.patch"
                TIMEOUT 60
                STATUS LLVM_VPTO_DL_STATUS
            )
            list(GET LLVM_VPTO_DL_STATUS 0 LLVM_VPTO_DL_CODE)
            if(NOT LLVM_VPTO_DL_CODE EQUAL 0 OR NOT EXISTS "${CANN_LLVM_PATCH_PATH}/feature-vpto-last3.patch")
                # The source does not carry SimtEntry, so the patch is required;
                # a failed download cannot be silently ignored.
                message(FATAL_ERROR "[ThirdParty][llvm] vpto patch download failed (code ${LLVM_VPTO_DL_CODE}) and the LLVM source lacks SimtEntry; the patch is required for the PTOAS build")
            endif()
            file(SHA256 "${CANN_LLVM_PATCH_PATH}/feature-vpto-last3.patch" LLVM_VPTO_DL_SHA256)
            if(LLVM_VPTO_DL_SHA256 STREQUAL "a49c1d3dd8ab78e93264712bc0d46deb536196a54abb2c2ee02abd914cd385e2")
                set(LLVM_VPTO_PATCH_FILE ${CANN_LLVM_PATCH_PATH}/feature-vpto-last3.patch)
                set(LLVM_VPTO_PATCH_READY TRUE)
                message(STATUS "[ThirdParty][llvm] vpto patch downloaded: ${LLVM_VPTO_PATCH_FILE}")
            else()
                message(FATAL_ERROR "[ThirdParty][llvm] vpto patch SHA256 mismatch (${LLVM_VPTO_DL_SHA256})")
            endif()
        endif()
    endif()

    if(LLVM_SOURCE_HAS_VPTO)
        message(STATUS "[ThirdParty][llvm] LLVM source already carries SimtEntry, skip vpto patch")
    elseif(LLVM_VPTO_PATCH_READY)
        message(STATUS "[ThirdParty][llvm] vpto patch ready: ${LLVM_VPTO_PATCH_FILE}")
    else()
    endif()
    message(WARNING "[ThirdParty][llvm] vpto patch unavailable; PTOAS build may fail with missing SimtEntry")

    set(LLVM_VPTO_PATCH_ARGS "")
    if(NOT LLVM_SOURCE_HAS_VPTO AND LLVM_VPTO_PATCH_READY)
        set(LLVM_VPTO_PATCH_ARGS PATCH_COMMAND patch -p1 < ${LLVM_VPTO_PATCH_FILE})
    endif()

    set(LLVM_PASSTHROUGH_VARS
        CMAKE_C_COMPILER_LAUNCHER CMAKE_CXX_COMPILER_LAUNCHER
        CMAKE_C_COMPILER CMAKE_CXX_COMPILER CMAKE_TOOLCHAIN_FILE
    )

    set(LLVM_SDK_CMAKE_ARGS)
    foreach(_VAR IN LISTS LLVM_PASSTHROUGH_VARS)
        if(DEFINED ${_VAR})
            list(APPEND LLVM_SDK_CMAKE_ARGS "-D${_VAR}=${${_VAR}}")
        endif()
    endforeach()

    set(COMMON_C_CXX_FLAGS "-fPIC -fstack-protector-strong -D_GLIBCXX_USE_CXX11_ABI=${CANN_CXX11_ABI}")
    if(CANN_THIRD_PARTY_C_FLAGS)
        set(LLVM_C_FLAGS "${CANN_THIRD_PARTY_C_FLAGS} ${COMMON_C_CXX_FLAGS}")
    else()
        set(LLVM_C_FLAGS "${COMMON_C_CXX_FLAGS}")
    endif()
    if(CANN_THIRD_PARTY_CXX_FLAGS)
        set(LLVM_CXX_FLAGS "${CANN_THIRD_PARTY_CXX_FLAGS} ${COMMON_C_CXX_FLAGS}")
    else()
        set(LLVM_CXX_FLAGS "${COMMON_C_CXX_FLAGS}")
    endif()
    set(LLVM_EXE_LINKER_FLAGS "-Wl,-z,relro,-z,now,-z,noexecstack -pie")
    set(LLVM_SHARED_LINKER_FLAGS "-Wl,-z,relro,-z,now,-z,noexecstack")

    ExternalProject_Add(cann_third_party_llvm
        URL ${REQ_URL}
        URL_HASH SHA256=59abea1c22e64933fad4de1671a61cdb934098793c7a31b333ff58dc41bff36c
        TIMEOUT 600
        DOWNLOAD_DIR ${CANN_LLVM_DOWNLOAD_PATH}
        SOURCE_DIR ${CANN_LLVM_SOURCE_PATH}
        ${LLVM_VPTO_PATCH_ARGS}
        SOURCE_SUBDIR llvm
        CMAKE_ARGS ${LLVM_SDK_CMAKE_ARGS}
            -DCMAKE_C_FLAGS=${LLVM_C_FLAGS}
            -DCMAKE_CXX_FLAGS=${LLVM_CXX_FLAGS}
            -DCMAKE_EXE_LINKER_FLAGS=${LLVM_EXE_LINKER_FLAGS}
            -DCMAKE_SHARED_LINKER_FLAGS=${LLVM_SHARED_LINKER_FLAGS}
            -DCMAKE_BUILD_TYPE=Release
            -DCMAKE_CXX_STANDARD=17
            -DCMAKE_POSITION_INDEPENDENT_CODE=ON
            -DCMAKE_VISIBILITY_INLINES_HIDDEN=ON
            -DCMAKE_INSTALL_PREFIX=${CANN_LLVM_INSTALL_PATH}
            -DLLVM_ENABLE_PROJECTS=mlir
            -DLLVM_TARGETS_TO_BUILD=Native
            -DLLVM_ENABLE_ZSTD=OFF
            -DLLVM_ENABLE_ASSERTIONS=OFF
            -DLLVM_INCLUDE_TESTS=OFF
            -DLLVM_INCLUDE_BENCHMARKS=OFF
            -DLLVM_INCLUDE_EXAMPLES=OFF
            -DMLIR_ENABLE_BINDINGS_PYTHON=ON  # llvm工程中会查找python3和pybind
            -DLLVM_PARALLEL_LINK_JOBS=2
        EXCLUDE_FROM_ALL TRUE
    )

    set(_CANN_LLVM_INCLUDE "${CANN_LLVM_INSTALL_PATH}/include" PARENT_SCOPE)
    set(_CANN_LLVM_CORE_LIBRARY "${CANN_LLVM_INSTALL_PATH}/lib/libLLVMCore.a" PARENT_SCOPE)
    set(_CANN_MLIR_IR_LIBRARY "${CANN_LLVM_INSTALL_PATH}/lib/libMLIRIR.a" PARENT_SCOPE)
    set(_CANN_MLIR_SUPPORT_LIBRARY "${CANN_LLVM_INSTALL_PATH}/lib/libMLIRSupport.a" PARENT_SCOPE)
endfunction()

function(__cann_add_llvm)
    set(CANN_LLVM_VERSION "19.1.7")
    set(CANN_LLVM_TAG "llvmorg-${CANN_LLVM_VERSION}")
    set(CANN_LLVM_URL "https://cann-3rd.obs.cn-north-4.myhuaweicloud.com/llvm/llvm-project-llvmorg-19.1.7.tar.gz")

    set(CANN_LLVM_SOURCE_PATH ${CANN_3RD_LIB_PATH}/llvm-19)
    set(CANN_LLVM_INSTALL_PATH ${CANN_3RD_LIB_PATH}/lib_cache/llvm-${CANN_LLVM_VERSION})
    set(CANN_LLVM_DOWNLOAD_PATH ${CANN_3RD_LIB_PATH}/pkg)
    set(CANN_LLVM_ARCHIVE ${CANN_LLVM_DOWNLOAD_PATH}/llvm-project-${CANN_LLVM_TAG}.tar.gz)
    set(CANN_LLVM_PATCH_PATH ${CANN_3RD_LIB_PATH}/patch)

    find_path(_CANN_LLVM_INCLUDE
        NAMES llvm/IR/Module.h
        PATH_SUFFIXES include
        PATHS ${CANN_LLVM_INSTALL_PATH}
        NO_DEFAULT_PATH
    )

    find_library(_CANN_LLVM_CORE_LIBRARY
        NAMES libLLVMCore.a
        PATH_SUFFIXES lib lib64
        PATHS ${CANN_LLVM_INSTALL_PATH}
        NO_DEFAULT_PATH
    )

    find_library(_CANN_MLIR_IR_LIBRARY
        NAMES libMLIRIR.a
        PATH_SUFFIXES lib lib64
        PATHS ${CANN_LLVM_INSTALL_PATH}
        NO_DEFAULT_PATH
    )

    find_library(_CANN_MLIR_SUPPORT_LIBRARY
        NAMES libMLIRSupport.a
        PATH_SUFFIXES lib lib64
        PATHS ${CANN_LLVM_INSTALL_PATH}
        NO_DEFAULT_PATH
    )

    include(FindPackageHandleStandardArgs)
    find_package_handle_standard_args(llvm
        FOUND_VAR llvm_FOUND
        REQUIRED_VARS
        _CANN_LLVM_INCLUDE
        _CANN_LLVM_CORE_LIBRARY
        _CANN_MLIR_IR_LIBRARY
        _CANN_MLIR_SUPPORT_LIBRARY
    )

    if(NOT llvm_FOUND OR FORCE_REBUILD_CANN_3RD)
        __cann_build_llvm()
    else()
        add_custom_target(cann_third_party_llvm)
    endif()

    set(CANN_THIRD_PARTY_LLVM_PATH ${CANN_3RD_LIB_PATH}/lib_cache/llvm-${CANN_LLVM_VERSION} CACHE PATH "CANN third party llvm path." FORCE)
endfunction()

__cann_add_llvm()
