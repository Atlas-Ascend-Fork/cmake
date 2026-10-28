# -----------------------------------------------------------------------------------------------------------
# Copyright (c) 2025 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.
# -----------------------------------------------------------------------------------------------------------
# makeself.cmake - 自定义 makeself 打包脚本

include(${CMAKE_CURRENT_LIST_DIR}/pkg_func.cmake)

set(CMAKE_SYSTEM_PROCESSOR ${CPACK_TARGET_ARCH})
# 设置 makeself 路径
set(MAKESELF_EXE ${CPACK_MAKESELF_PATH}/makeself.sh)
set(MAKESELF_HEADER_EXE ${CPACK_MAKESELF_PATH}/makeself-header.sh)
if(NOT MAKESELF_EXE)
    message(FATAL_ERROR "makeself not found!")
endif()

list(LENGTH CPACK_COMPONENTS_ALL len_components)
list(LENGTH CPACK_PACKAGE_PARAM_NAME len_share_info_names)
if(NOT len_components EQUAL len_share_info_names)
    message(FATAL_ERROR "CPACK_COMPONENTS_ALL and CPACK_PACKAGE_PARAM_NAME is not one-to-one mapping.")
endif()

set(STAGING_DIR "${CPACK_CMAKE_BINARY_DIR}/_CPack_Packages/makeself_staging")

math(EXPR len_components "${len_components} - 1")
foreach(index RANGE ${len_components})
    list(GET CPACK_COMPONENTS_ALL ${index} component)
    list(GET CPACK_PACKAGE_PARAM_NAME ${index} share_info_name)
    list(GET CPACK_CMAKE_SOURCE_DIR ${index} source_dir)
    list(GET CPACK_ENABLE_DEVICE ${index} enable_device)
    pack_run_package("${component}" "${share_info_name}" "${source_dir}" "${enable_device}")
endforeach()
