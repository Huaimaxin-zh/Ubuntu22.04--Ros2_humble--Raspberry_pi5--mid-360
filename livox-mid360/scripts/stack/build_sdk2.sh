#!/usr/bin/env bash
# 编译锁定的官方 Livox-SDK2 加本次符号绑定补丁，安装到 xin 的用户目录。
# 不需要 sudo，不覆盖 /usr/local 中可能存在的其他版本。
set -eo pipefail
setup_dir=/home/xin/livox_stack_setup
sdk_source=/home/xin/src/Livox-SDK2
sdk_build=/home/xin/src/Livox-SDK2/build-pi5
sdk_install=/home/xin/livox_sdk2
sdk_patch="$setup_dir/patches/sdk-spdlog-symbol-binding.patch"
exec > >(tee "$setup_dir/build-sdk2.log") 2>&1
printf 'RUNNING\n' > "$setup_dir/sdk2.status"
trap 'result=$?; printf "EXIT=%s\n" "$result" > "$setup_dir/sdk2.status"' EXIT

# 确认锁定的官方提交，避免文档和实际构建版本不一致。
test "$(git -C "$sdk_source" rev-parse HEAD)" = c0796f04c143143899c87a773d9f6b7136453c0b

# 补丁修复 SDK 内嵌 spdlog 与 ROS2 系统 spdlog 的符号冲突。
# 先核对留档字节；缺失或不一致时停止，避免重新编出未修复的 SDK。
if [ ! -f "$sdk_patch" ]; then
    echo "缺少补丁：$sdk_patch；请先按仓库说明复制到该路径。" >&2
    exit 1
fi
if ! printf '%s  %s\n' \
    663a32a45aa5d067d503a1e9bc5e6e176b0d28951dc3fb7e0d47a980ef8d9737 \
    "$sdk_patch" | sha256sum --check --status; then
    echo 'SDK 补丁 SHA256 不匹配，停止构建；不要跳过校验。' >&2
    exit 1
fi

# 反向检查能通过，表示这一份补丁已应用；无需再次修改源码。
if git -C "$sdk_source" apply --reverse --check "$sdk_patch" >/dev/null 2>&1; then
    echo 'SDK 符号绑定补丁已经应用，继续构建。'
# 正向检查通过才应用；不会强制覆盖用户冲突的自定义修改。
elif git -C "$sdk_source" apply --check "$sdk_patch"; then
    git -C "$sdk_source" apply "$sdk_patch"
    echo 'SDK 符号绑定补丁应用完成。'
else
    echo 'SDK 源码与补丁不兼容，停止构建；请先检查差异。' >&2
    exit 1
fi

# Release 开启优化；前缀指定安装结果保存在个人目录。
cmake -S "$sdk_source" -B "$sdk_build" \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$sdk_install"
# 单线程只构建 SDK 库，避免四核同时编译导致内存不足。
cmake --build "$sdk_build" --target livox_lidar_sdk_shared livox_lidar_sdk_static --parallel 1
# sdk_core 的安装脚本仅安装库及公开头文件，不安装无需使用的 sample 程序。
cmake --install "$sdk_build/sdk_core"
test -f "$sdk_install/lib/liblivox_lidar_sdk_shared.so"
test -f "$sdk_install/include/livox_lidar_api.h"
ldd "$sdk_install/lib/liblivox_lidar_sdk_shared.so"
echo 'SDK2_BUILD_OK'
