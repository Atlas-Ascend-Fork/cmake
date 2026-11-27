<!-- -----------------------------------------------------------------------------------------------------------
 Copyright (c) 2026 Huawei Technologies Co., Ltd.
 This program is free software, you can redistribute it and/or modify it under the terms and conditions of
 CANN Open Software License Agreement Version 2.0 (the "License").
 Please refer to the License for details. You may not use this file except in compliance with the License.
 THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
 INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
 See LICENSE in the root of the software repository for the full text of the License.
----------------------------------------------------------------------------------------------------------- -->

# 公共 API 参考

`function/prepare.cmake` 中定义的函数是框架的公共 API，被 CANN 组件仓的 CMakeLists.txt 调用。修改签名或行为是跨仓破坏性变更。

## 初始化

### `init_cann_project([PRODUCT_SIDE <host|device>] [PREPEND_MODULE_PATH])`

初始化工程，设置 C++17、ccache、安装路径变量、模块路径等。有幂等保护，联合构建时多次调用只在首次生效。

| 参数 | 说明 |
|------|------|
| `PRODUCT_SIDE` | `host` 或 `device`，影响 ABI 和源码目录 |
| `PREPEND_MODULE_PATH` | 将 `modules/` 加入 `CMAKE_MODULE_PATH` |

**调用时机**：`project()` 之后。

## 包与版本声明

### `set_cann_package(name VERSION <version>)`

声明包名和版本号。必须在其它 `set_cann_*` 函数之前调用。

```cmake
set_cann_package(runtime VERSION "8.0.0")
```

### `set_cann_build_dependencies(pkg_name depend)`

声明构建依赖。`depend` 为版本约束字符串，支持 `>=`/`>`/`<=`/`<` 前缀（省略则按精确匹配），`CUR_MAJOR_MINOR_VER` 会被替换为当前包的主次版本号。

```cmake
set_cann_build_dependencies(runtime "CUR_MAJOR_MINOR_VER")
```

### `set_cann_run_dependencies(pkg_name depend)`

声明运行依赖。同时影响打包时的 deb/rpm 依赖信息。

### `check_cann_pkg_build_deps(pkg_name)`

检查构建依赖是否满足。调用 `scripts/version/check_build_dependencies.py`。仅 `TOPLEVEL_PROJECT ON` 时生效。

### `check_cann_build_tool(tool_name [HINT <message>])`

检查构建依赖的工具是否已安装，未安装则 `FATAL_ERROR` 终止。多仓联编时通过全局属性确保同一工具只检查一次。

| 参数 | 说明 |
|------|------|
| `tool_name` | 必选，工具名（如 `cmake`、`protoc`） |
| `HINT` | 可选，安装提示信息，拼接到报错消息末尾 |

`TOPLEVEL_PROJECT ON` 或 `ENABLE_UNIFIED_BUILD` 时生效。

```cmake
check_cann_build_tool(protoc HINT "Run: pip install protobuf")
```

## Device 构建

### `add_cann_device_project(component)`

注册 device 侧构建工程。通过 ExternalProject 启动独立 CMake 进程，引入 `${CMAKE_SOURCE_DIR}/cmake/device/` 下的 CMakeLists.txt，使用 `aarch64-hcc-toolchain.cmake` 交叉编译。

| 行为条件 | 说明 |
|---------|------|
| `TOPLEVEL_PROJECT OFF` | 直接返回（多仓联编时由 superbuild 统一管理 device 构建） |
| `ENABLE_BUILD_DEVICE` 为 `FALSE` | 直接返回（跳过 device 编译） |

仅子仓独立构建时调用。多仓联编时 device 构建由 `superbuild/CMakeLists.txt` 通过 ExternalProject 直接处理，不经过此函数。

## 打包配置

### `set_cann_cpack_config(component [options...])`

配置 CPack 打包参数。仅 `TOPLEVEL_PROJECT ON` 或 `ENABLE_UNIFIED_BUILD` 时生效。

| 选项 | 说明 |
|------|------|
| `TGZ` | 生成 TGZ 包（而非 makeself/run 包） |
| `ENABLE_DEVICE` | 是否解压 `device-<component>.tar.gz` |
| `PACKAGE_TYPE` | 包类型：`run`/`rpm`/`deb` |
| `COMPUTE_UNIT` | 芯片型号 |
| `SHARE_INFO_NAME` | share/info 目录下的名称（与 component 不一致时使用） |
| `OUTPUT` | 输出路径 |
| `ARCHIVE_FILE_NAME` | 归档文件名 |

### `set_cann_subprj_package([SUPERBUILD])`

子工程打包。`SUPERBUILD` 模式将所有指定包统一打包为 TGZ。

### `cann_pack_targets_and_files(OUTPUT <path> OUTPUT_TARGET <name> [TARGETS ...] [FILES ...] [options...])`

打包目标文件和普通文件为 tar.gz。

| 选项 | 说明 |
|------|------|
| `OUTPUT` | 输出文件路径（必选） |
| `OUTPUT_TARGET` | 输出目标名（必选） |
| `TARGETS` | 要打包的构建目标列表 |
| `FILES` | 要打包的文件列表 |
| `MANIFEST` | manifest 文件名（相对路径） |
| `TAR_ROOT_DIR` | tar 包内根目录名 |
| `SIZE_LIMIT` | 大小限制（KB），Release 模式下超出则报错 |
| `GEN_INI` | 传入该选项时生成 .ini 文件（另需 `CANN_VERSION_CURRENT_PACKAGE` 以解析版本号） |

`FILES` 中的文件会作为归档命令的构建依赖；文件变化时重新生成归档。

归档权限：`EXECUTABLE` 目标在暂存后显式 `chmod 750`（`rwxr-x---`，与 umask 无关——可执行程序须带 x 才能运行）；其余成员由 `tar --mode=u=rwX,g=rX,o=` 规整——动态库/目录为 `750`、普通文件（含生成的 `.ini` 与 manifest `.cfg`）为 `640`（`rw-r-----`）。动态库无 x 亦可加载，故不强制。

## 第三方依赖

### `add_cann_third_party(name)`

引入 `third_party/<name>.cmake` 脚本。仅 `TOPLEVEL_PROJECT ON` 或 `ENABLE_UNIFIED_BUILD` 时生效。

```cmake
add_cann_third_party(boost)
```

### `find_cann_package(name ...)`

`find_package` 的包装。独立构建时正常调用 `find_package`。多仓联编时的行为参见 [superbuild/internals.md](../superbuild/internals.md)。

## 目标操作

### `clone_cann_target(ORIGIN <target> OUTPUT <target> [IGNORE_PROP ...])`

克隆 target 的属性到新 target。可跳过指定属性。

| 参数 | 说明 |
|------|------|
| `ORIGIN` | 源 target（必选） |
| `OUTPUT` | 新 target 名（必选） |
| `IGNORE_PROP` | 要跳过（不克隆）的属性列表，取值见下表 |

`IGNORE_PROP` 可识别的属性：

| 属性值 | 说明 |
|------|------|
| `SOURCES` | 源文件 |
| `INCLUDE_DIRECTORIES` | 头文件搜索目录 |
| `LINK_LIBRARIES` | 链接库 |
| `LINK_DIRECTORIES` | 链接库搜索目录 |
| `COMPILE_DEFINITIONS` | 编译宏定义 |
| `COMPILE_OPTIONS` | 编译选项 |
| `LINK_OPTIONS` | 链接选项 |

```cmake
clone_cann_target(ORIGIN ccl_kernel OUTPUT aicpu_custom IGNORE_PROP LINK_LIBRARIES)
```

### `generate_cann_stub_library(name [OUTPUT_NAME <name>])`

生成打桩库（空实现的共享库），用于链接时符号解析。

### `add_cann_subdirectories_relative(base_dir <dir...>)`

通过相对父目录方式添加子目录。

## 版本信息

### `gen_cann_version_header(pkg_name [VERSION <ver>] [component])`

生成版本号头文件 `${CMAKE_BINARY_DIR}/include/version/<pkg>_version.h`，并安装到 `<arch>-linux/include/version/`。

增量构建会跟踪版本头生成脚本的修改，脚本更新后重新生成头文件。

### `add_cann_version_info_targets([EXTRA_FIELDS <key=value>...])`

为每个已声明的包生成 `version.<pkg>.info` 文件的自定义目标。文件内容依次为
`Version`、`version_dir`、运行依赖版本、`repository_url`、`commit_id`、`timestamp`；
`repository_url` 与 `commit_id` 同进同出，位于 `timestamp` 之前。

仓库信息采用"生产者 → JSON → 消费者"两级流水线：构建期运行生产者脚本生成
`${CMAKE_BINARY_DIR}/repo_info.<pkg>.json`，消费者只做 schema 校验并直接消费。

- `CANN_REPO_INFO_GEN_SCRIPT` 指定的自定义生产者（支持用户自定义，适用于特殊场景）；
- 未指定时使用框架内置 `scripts/version/gen_repo_info.py`：从组件仓 git 取
  `origin` 地址与 HEAD。

生产者契约：接收 `--package-name <pkg> --repo-dir <dir> --output <file>`；
**写最终值**——URL 归一化（`git@`/`ssh://git@` 含端口转 `https://`、剥离 http(s)
userinfo 凭据、去末尾 `.git`）与 `commit_id` 统一小写由生产者完成；仅 `git@` /
`ssh://git@` 形态保证转换为 https，其余形态（含 `user@host:path`）仅去末尾
`.git`、原样保留；产物为分组
JSON（schema 支持多包，消费者按包名查找本包条目）：

```json
{
    "npu-runtime": {
        "repository_url": "https://gitcode.com/cann/runtime",
        "commit_id": "347883e8b4f97b58321465b0102f671e8f97995a"
    }
}
```

探测失败（非 git 仓库、无 origin、git 不可用等）是合法空态——写 `{}` 并告警，
构建继续；origin 为本地路径或 `file://` 形态时同样按空态处理（避免构建机路径进入
发布制品）；"数据存在但残缺"（如确认信息存在但内容不完整）属硬错误——
非零退出，构建失败。特殊场景的生产者**由使用方自行实现**并经
`CANN_REPO_INFO_GEN_SCRIPT` 挂入，本仓不提供、不维护特定场景的解析脚本，
相应解析逻辑的维护责任归使用方。

消费者校验：条目仅允许 `repository_url` / `commit_id` 两键且必须同时存在；
`commit_id` 为 40 位十六进制；包名键非法、未知键、重复键、空值、值内换行均拒绝，
schema 非法时构建失败；**文件为多包时须整体合法**（任一条目非法即构建失败，
脏条目 fail-fast）；**缺本包条目时告警（含包名与文件路径）并省略两字段**。

`CANN_REPO_INFO_GEN_SCRIPT` 传入方式：`cmake -D...`，或经本仓 `build.sh
--cmake-extra-args` 传导；另支持同名环境变量兜底（优先级 `-D`/cache >
`ENV{CANN_REPO_INFO_GEN_SCRIPT}` > 未设置用框架内置生产者），适用于组件仓单仓
build.sh 无透传参数的场景，env 派生值不回写 cache（每次 configure 现读现用）。
相对路径以 `CMAKE_SOURCE_DIR` 为基准归一，请使用**绝对路径**。

多仓联编时按 `CANN_PACKAGE_DIR_<pkg>` 映射解析组件仓目录，单仓时使用调用点源码目录。

可选参数 `EXTRA_FIELDS`（可多个 `key=value`）：按给定顺序追加到 `timestamp` 之后，
用于组件专有字段，框架不解释其业务含义。保留键（`Version`、`version_dir`、`timestamp`、
`repository_url`、`commit_id` 及 `required_package_` 前缀）不可注入；关键词拼错或缺少值会
在 configure 阶段报错。示例：

```cmake
add_cann_version_info_targets(EXTRA_FIELDS "host_only=true")
```

## 签名

### `add_cann_sign_file(INPUT <path> CONFIG <path> RESULT_VAR <var> [options...])`

添加代码签名步骤。

| 参数 | 说明 |
|------|------|
| `INPUT` | 待签名文件（必选） |
| `CONFIG` | 签名配置文件（必选） |
| `RESULT_VAR` | 接收签名后文件路径的变量（必选） |
| `OUTPUT_TARGET` | 自定义目标名 |
| `DEPENDS` | 额外依赖 |
| `VERSION` | 版本号（必选） |

签名脚本通过 `CUSTOM_SIGN_SCRIPT` 或 `ENABLE_SIGN` 控制。
