#!/usr/bin/env bash
# 中文说明：本文件仅保存此次现场 SDK 恢复命令，不是独立的一键重建脚本。
# 运行前必须已有 RAM 中的干净 SDK 源码和 GCC/sysroot；重启后这些目录会消失。
# 同目录部分精确源码补丁不可重复执行；本文件已有安装目标也必须与输出一致。
# 本脚本只安装 SDK 头文件和共享库到用户目录，不负责下载前置文件或修复系统。
# 命令失败就退出，tee 管道也要保留 CMake 的真实失败状态。
set -eo pipefail
# RAM 中专用于 SDK 的现场目录。
sdk_task_root=/dev/shm/livox-sdk-clean-xin
# 固定官方版本的干净 SDK 源码；本脚本不重新克隆或下载它。
sdk_clean_source="$sdk_task_root/source"
# 与源码分开保存的临时 SDK 构建目录。
sdk_clean_build="$sdk_task_root/build"
# 最终持久 SDK 目录，供驱动查找 include 和 lib。
sdk_install_prefix=/home/xin/livox_runtime/sdk
# 现场已校验、解压的干净 GCC 和系统开发文件。
sdk_toolchain=/dev/shm/livox-recovery-xin/toolchain

# 确认 SDK 的 CMake 源文件存在；不满足条件就停止。
test -f "$sdk_clean_source/sdk_core/CMakeLists.txt"
# 确认指定 C++ 编译器存在且可执行，不回退到原系统工具。
test -x "$sdk_toolchain/usr/bin/aarch64-linux-gnu-g++-11"
# 确认指定 C 编译器存在且可执行。
test -x "$sdk_toolchain/usr/bin/aarch64-linux-gnu-gcc-11"

# Install only these three clean public headers into the isolated user prefix.
# No files in /usr/local, /opt, or the original source tree are changed.
# 只在用户前缀创建 include/lib 目录；不改 /usr/local、/opt 或原源码。
mkdir -p "$sdk_install_prefix/include" "$sdk_install_prefix/lib"
# 依次处理三个公开头文件：API、数据定义和配置结构。
for sdk_header in livox_lidar_api.h livox_lidar_def.h livox_lidar_cfg.h; do
  # 目标已经存在时先比较内容，避免直接覆盖其他版本。
  if test -e "$sdk_install_prefix/include/$sdk_header"; then
    # cmp 不一致会返回失败，随后整个脚本停止。
    cmp "$sdk_clean_source/include/$sdk_header" "$sdk_install_prefix/include/$sdk_header"
  else
    # 仅目标不存在时复制；644 表示所有者读写、其他用户只读。
    install -m 644 "$sdk_clean_source/include/$sdk_header" "$sdk_install_prefix/include/$sdk_header"
  fi
done
# 输出头文件就绪路径，供驱动构建确认前置步骤完成。
echo "SDK_HEADERS_READY=$sdk_install_prefix/include"

# Make 和 CMake 均限制单线程，降低树莓派编译时的内存需求。
export MAKEFLAGS=-j1 CMAKE_BUILD_PARALLEL_LEVEL=1
# 以下为同一条 CMake 配置命令，各参数按顺序说明：
# -S / -B：指定干净源码和 RAM 构建目录。
# CMAKE_C_COMPILER / CMAKE_CXX_COMPILER：指定干净 GCC 11 的 C/C++ 编译器。
# C/CXX_FLAGS 中 --sysroot：使用干净开发文件；-fmax-errors=2：最多报告两个错误。
# Release：发布构建；INSTALL_PREFIX：记录用户目录安装前缀。
# 2>&1 合并标准输出和错误输出，tee 同时显示并保存配置日志。
cmake -S "$sdk_clean_source" -B "$sdk_clean_build" \
  -DCMAKE_C_COMPILER="$sdk_toolchain/usr/bin/aarch64-linux-gnu-gcc-11" \
  -DCMAKE_CXX_COMPILER="$sdk_toolchain/usr/bin/aarch64-linux-gnu-g++-11" \
  -DCMAKE_C_FLAGS="--sysroot=$sdk_toolchain -fmax-errors=2" \
  -DCMAKE_CXX_FLAGS="--sysroot=$sdk_toolchain -fmax-errors=2" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$sdk_install_prefix" \
  2>&1 | tee "$sdk_task_root/configure.log"

# The ROS2 driver links the shared SDK. This avoids building the duplicate
# static library and the SDK's samples, which are unnecessary for the driver.
# 只构建驱动需要的共享库，单线程执行；不重复构建静态库或示例程序。
cmake --build "$sdk_clean_build" --target livox_lidar_sdk_shared --parallel 1 \
  2>&1 | tee "$sdk_task_root/build.log"
# 记录刚才生成的共享库完整路径。
sdk_shared_library="$sdk_clean_build/sdk_core/liblivox_lidar_sdk_shared.so"
# 要求输出文件存在且非空；这不代替后续格式和依赖检查。
test -s "$sdk_shared_library"
# 查看文件类型；现场应显示 ARM aarch64 的 ELF 共享库。
file "$sdk_shared_library"
# 最终库已经存在时先确认内容一致，不静默覆盖其他版本。
if test -e "$sdk_install_prefix/lib/liblivox_lidar_sdk_shared.so"; then
  # 内容不一致则停止，留待人工确认版本。
  cmp "$sdk_shared_library" "$sdk_install_prefix/lib/liblivox_lidar_sdk_shared.so"
else
  # 仅目标不存在时安装；755 允许所有者读写执行、其他用户读取执行。
  install -m 755 "$sdk_shared_library" "$sdk_install_prefix/lib/liblivox_lidar_sdk_shared.so"
fi
# 显示最终持久库的动态依赖及实际解析路径；不修改系统动态库。
ldd "$sdk_install_prefix/lib/liblivox_lidar_sdk_shared.so"
# 输出最终 SDK 库位置，驱动通过此路径链接。
echo "SDK_SHARED_READY=$sdk_install_prefix/lib/liblivox_lidar_sdk_shared.so"
