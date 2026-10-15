# -----------------------------------------------------------------------------------------------------------
# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.
# -----------------------------------------------------------------------------------------------------------
# 打包公共函数

# 打包前处理
function(pre_package_process component share_info_name source_dir enable_device package_dir suffix)
    set(CANN_PACKAGE_DIR "${package_dir}")

    if(enable_device)
        execute_process(
            COMMAND tar --keep-old-files -zxpf device-${component}.tar.gz
            WORKING_DIRECTORY "${CANN_PACKAGE_DIR}"
            RESULT_VARIABLE RETCODE
        )
        if(RETCODE)
            message(FATAL_ERROR "Extract device-${component}.tar.gz failed, return code is ${RETCODE}.")
        endif()

        file(REMOVE "${CANN_PACKAGE_DIR}/device-${component}.tar.gz")
    endif()

    if(CPACK_CANN_PRE_PKG_${component})
        include(${CPACK_CANN_PRE_PKG_${component}})
    endif()

    execute_process(
        COMMAND python3 ${CMAKE_CURRENT_LIST_DIR}/package.py --pkg_name ${share_info_name} --chip_name ${CPACK_SOC}
                --os_arch linux-${CMAKE_SYSTEM_PROCESSOR} --version_dir ${CPACK_PACKAGE_VERSION} --delivery_dir ${CANN_PACKAGE_DIR}
                --source_dir ${source_dir} --suffix ${suffix} --command-output "${STAGING_DIR}/makeself.txt"
        WORKING_DIRECTORY ${CPACK_CMAKE_BINARY_DIR}
        OUTPUT_VARIABLE result
        ERROR_VARIABLE error
        RESULT_VARIABLE code
        OUTPUT_STRIP_TRAILING_WHITESPACE
    )
    if (NOT code EQUAL 0)
        message(FATAL_ERROR "Filelist generation failed: ${result} ${error}")
    endif()
endfunction()

# 打包run包
function(pack_run_package component share_info_name source_dir enable_device)
    # 创建临时安装目录
    file(REMOVE_RECURSE "${STAGING_DIR}")
    file(MAKE_DIRECTORY "${STAGING_DIR}")

    # 执行安装到临时目录
    execute_process(
        COMMAND "${CMAKE_COMMAND}" --install "${CPACK_CMAKE_BINARY_DIR}" --prefix "${STAGING_DIR}" --component "${component}"
        RESULT_VARIABLE INSTALL_RESULT
    )

    if(NOT INSTALL_RESULT EQUAL 0)
        message(FATAL_ERROR "Installation to staging directory failed: ${INSTALL_RESULT}")
    endif()

    pre_package_process("${component}" "${share_info_name}" "${source_dir}" "${enable_device}" "${STAGING_DIR}" "run")

    # makeself打包
    file(STRINGS ${STAGING_DIR}/makeself.txt script_output)
    string(REPLACE " " ";" makeself_param_string "${script_output}")
    string(REGEX MATCH "cann.*\\.run" package_name "${makeself_param_string}")
    file(REMOVE "${STAGING_DIR}/makeself.txt")

    list(LENGTH makeself_param_string LIST_LENGTH)
    math(EXPR INSERT_INDEX "${LIST_LENGTH} - 2")
    list(INSERT makeself_param_string ${INSERT_INDEX} "${STAGING_DIR}")

    message(STATUS "script output: ${script_output}")
    message(STATUS "makeself: ${makeself_param_string}")
    message(STATUS "package: ${package_name}")

    if(NOT DEFINED CPACK_HELP_HEADER_PATH)
        set(CPACK_HELP_HEADER_PATH "share/info/${share_info_name}/script/help.info")
    endif()

    if(NOT DEFINED CPACK_INSTALL_PATH)
        set(CPACK_INSTALL_PATH "share/info/${share_info_name}/script/install.sh")
    endif()

    execute_process(COMMAND bash ${MAKESELF_EXE}
            --header ${MAKESELF_HEADER_EXE}
            --help-header ${CPACK_HELP_HEADER_PATH}
            ${makeself_param_string} ${CPACK_INSTALL_PATH}
            WORKING_DIRECTORY ${STAGING_DIR}
            RESULT_VARIABLE EXEC_RESULT
            ERROR_VARIABLE  EXEC_ERROR
    )

    if(NOT EXEC_RESULT EQUAL 0)
        message(FATAL_ERROR "makeself packaging failed: ${EXEC_ERROR}")
    endif()

    if(CPACK_CMAKE_INSTALL_PREFIX STREQUAL STAGING_DIR)
        return()
    endif()

    execute_process(
        COMMAND ${CMAKE_COMMAND} -E make_directory ${CPACK_CMAKE_INSTALL_PREFIX}
        RESULT_VARIABLE MKDIR_INSTALL_PREFIX
    )

    if(MKDIR_INSTALL_PREFIX EQUAL 0)
        execute_process(
            COMMAND find . -name "cann-*.run"
            COMMAND xargs -I {} cp {} ${CPACK_CMAKE_INSTALL_PREFIX}/
            WORKING_DIRECTORY ${STAGING_DIR}
            RESULT_VARIABLE EXEC_RESULT
            ERROR_VARIABLE  EXEC_ERROR
        )

        if(NOT "${EXEC_RESULT}" STREQUAL "0")
            message(FATAL_ERROR "Failed to copy run files: ${EXEC_ERROR}")
        else()
            message(STATUS "Build pkg success: ${CPACK_CMAKE_INSTALL_PREFIX}/${package_name}")
        endif()
    else()
        message(FATAL_ERROR "Failed to mkdir new directory: ${CPACK_CMAKE_INSTALL_PREFIX}")
    endif()
endfunction()
