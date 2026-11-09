#!/usr/bin/env bash
# 中文说明：本文件仅保存此次现场恢复命令，不是一键安装或一键重建脚本。
# 它依赖已准备的 RAM 工具链、持久 ROS/SDK/驱动，以及检查器 C++ 源文件。
# /dev/shm 内容重启后消失；同目录部分补丁只能匹配一次旧源码，不可重复执行。
# 本文件编译原生检查器，避免 Python 逐点解码影响点云和 IMU 频率测量。
# 命令或管道任一阶段失败都停止，避免安装未成功编译的检查器。
set -eo pipefail
# 此次树莓派用户目录中的完整运行环境。
root=/home/xin/livox_runtime
# 临时源码和编译结果放 RAM；本脚本不会准备其中的工具链。
task_root=/dev/shm/livox-recovery-xin
# 指定已经校验、解压的干净编译器和开发文件。
toolchain_root="$task_root/toolchain"
# 加载独立 ROS、SDK、消息类型及本次 DDS 环境。
source "$root/env.sh"
# CMake 依次查找驱动包、干净 ROS 和私有 Ubuntu 依赖。
export CMAKE_PREFIX_PATH="$root/install/livox_ros_driver2:$root/ros-clean/opt/ros/humble:$root/ubuntu-clean/usr"
# 创建 RAM 中的小工程目录；-p 允许目录已经存在。
mkdir -p "$task_root/native-verifier-source"
# 将持久保存的检查器源码复制到临时工程。
cp "$root/verify_livox_stream.cpp" "$task_root/native-verifier-source/"
# 将两条 EOF 标记之间的内容写成 CMakeLists.txt；引号禁止 Shell 展开变量。
cat > "$task_root/native-verifier-source/CMakeLists.txt" <<'EOF'
# 以下为 CMake 文件内容：要求 CMake 版本至少为 3.14。
cmake_minimum_required(VERSION 3.14)
# 定义只使用 C++ 的工程。
project(livox_stream_verifier LANGUAGES CXX)
# 查找 ROS2 的 ament 构建辅助模块；REQUIRED 表示找不到就报错。
find_package(ament_cmake REQUIRED)
# 查找 ROS2 C++ 客户端库，用于创建节点和订阅话题。
find_package(rclcpp REQUIRED)
# 查找驱动生成的 CustomMsg/CustomPoint 消息接口。
find_package(livox_ros_driver2 REQUIRED)
# 查找标准 IMU 消息接口。
find_package(sensor_msgs REQUIRED)
# 将这一份 C++ 源码编译成 verify_livox_stream 可执行程序。
add_executable(verify_livox_stream verify_livox_stream.cpp)
# 检查器目标使用 C++14；PRIVATE 表示仅作用于此目标。
target_compile_features(verify_livox_stream PRIVATE cxx_std_14)
# 为目标添加这些 ROS2 包的头文件、链接库与构建依赖。
ament_target_dependencies(verify_livox_stream rclcpp livox_ros_driver2 sensor_msgs)
EOF
# 以下为同一条 CMake 配置命令，参数按顺序解释：
# -S / -B：指定临时源码目录和编译目录。
# Release：发布构建；CMAKE_CXX_COMPILER：指定干净 GCC 11。
# CMAKE_SYSROOT：使用干净系统开发文件；包查找不被重定向到 sysroot。
# CMAKE_CXX_FLAGS：最多报告两个错误，加入私有 Ubuntu 头文件目录。
# console_bridge_DIR：显式指定私有 console_bridge 的 CMake 配置。
cmake -S "$task_root/native-verifier-source" -B "$task_root/native-verifier-build" \
 -DCMAKE_BUILD_TYPE=Release \
 -DCMAKE_CXX_COMPILER="$toolchain_root/usr/bin/aarch64-linux-gnu-g++-11" \
 -DCMAKE_SYSROOT="$toolchain_root" -DCMAKE_FIND_ROOT_PATH_MODE_PACKAGE=NEVER \
 -DCMAKE_CXX_FLAGS="-fmax-errors=2 -I$root/ubuntu-clean/usr/include" \
 -Dconsole_bridge_DIR="$root/ubuntu-clean/usr/lib/aarch64-linux-gnu/console_bridge/cmake"
# 执行构建；--parallel 1 为单线程，降低树莓派内存占用。
cmake --build "$task_root/native-verifier-build" --parallel 1
# 创建持久二进制目录，重启后仍保留编译好的检查器。
mkdir -p "$root/bin"
# 安装程序；700 允许所有者读写执行，不授予其他用户访问权限。
install -m 700 "$task_root/native-verifier-build/verify_livox_stream" "$root/bin/verify_livox_stream"
