#!/usr/bin/env bash
# 编译官方 Livox-SDK2；仅将头文件与动态/静态库安装到 xin 的用户目录。
# 不需要 sudo，不覆盖 /usr/local 中可能存在的其他版本。
set -eo pipefail
setup_dir=/home/xin/livox_stack_setup
sdk_source=/home/xin/src/Livox-SDK2
sdk_build=/home/xin/src/Livox-SDK2/build-pi5
sdk_install=/home/xin/livox_sdk2
exec > >(tee "$setup_dir/build-sdk2.log") 2>&1
printf 'RUNNING\n' > "$setup_dir/sdk2.status"
trap 'result=$?; printf "EXIT=%s\n" "$result" > "$setup_dir/sdk2.status"' EXIT

# 确认锁定的官方提交，避免文档和实际构建版本不一致。
test "$(git -C "$sdk_source" rev-parse HEAD)" = c0796f04c143143899c87a773d9f6b7136453c0b
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
