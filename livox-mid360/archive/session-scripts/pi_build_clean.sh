#!/usr/bin/env bash
# 中文说明：本文件仅保存此次现场恢复命令，不是一键安装或一键重建脚本。
# 前提是已经准备好 RAM 中的源码和干净工具链，以及用户目录中的 ROS/SDK/依赖。
# /dev/shm 内容在重启后消失；同目录部分精确补丁不可重复执行。
# 本脚本会编译并安装到下方 runtime_root；阅读留档不代表需要现在执行。
# 任一命令失败就停止；管道中的编译失败也必须传回，避免 tee 保存日志后掩盖错误。
set -eo pipefail
# 内存工作目录保存源码、编译缓存和日志，以减少 SD 卡中间文件写入。
task_root=/dev/shm/livox-recovery-xin
# 最终运行环境安装到持久用户目录，重启后仍保留。
runtime_root=/home/xin/livox_runtime
# 独立 ROS Humble 的安装前缀；本次没有替换系统 /opt/ros。
clean_ros="$runtime_root/ros-clean/opt/ros/humble"
# 现场已校验、解压的干净 GCC 和系统开发文件，位于 RAM 中。
toolchain_root="$task_root/toolchain"
# 清除当前脚本进程继承的旧工作区、Python 和动态库路径，避免混用损坏文件。
unset AMENT_PREFIX_PATH CMAKE_PREFIX_PATH COLCON_PREFIX_PATH PYTHONPATH LD_LIBRARY_PATH
# 加载刚才指定的干净 ROS 环境。
source "$clean_ros/local_setup.bash"
# CMake 搜索干净 ROS 和私有 Ubuntu 依赖的安装前缀。
export CMAKE_PREFIX_PATH="$clean_ros:$runtime_root/ubuntu-clean/usr"
# Python 优先使用私有纯 Python 包、NumPy 等模块，然后保留 ROS 设置的路径。
export PYTHONPATH="$runtime_root/python-clean:$runtime_root/ubuntu-clean/usr/lib/python3/dist-packages:$PYTHONPATH"
# 动态链接器优先加载私有 SDK、BLAS、LAPACK 和 Ubuntu 库，最后保留 ROS 库路径。
export LD_LIBRARY_PATH="$runtime_root/sdk/lib:$runtime_root/ubuntu-clean/usr/lib/aarch64-linux-gnu/blas:$runtime_root/ubuntu-clean/usr/lib/aarch64-linux-gnu/lapack:$runtime_root/ubuntu-clean/usr/lib/aarch64-linux-gnu:$LD_LIBRARY_PATH"
# 分别约束 Make 和 CMake 的并行度为 1，降低编译时的内存需求。
export MAKEFLAGS=-j1 CMAKE_BUILD_PARALLEL_LEVEL=1
# 进入已经存在的 RAM 工作目录；本脚本不负责下载或准备前置文件。
cd "$task_root"
# 以下反斜杠连接的是同一条 colcon 命令，参数按出现顺序说明：
# --log-base：将 colcon 日志放入 RAM 中的 log-clean。
# --base-paths：从独立驱动副本查找包，不改用户原工作区。
# --build-base / --install-base：中间文件放 RAM，最终程序安装到持久运行目录。
# --cmake-args：后面的 -D 参数交给 CMake。
# ROS_EDITION=ROS2 / DISTRO_ROS=humble：选择 ROS2 Humble 的消息生成与链接分支。
# CMAKE_BUILD_TYPE=Release：发布构建；BUILD_TESTING=OFF：不构建测试目标。
# AMENT_CMAKE_SYMLINK_INSTALL=OFF：复制安装，避免运行文件通过链接依赖 RAM 源码。
# CMAKE_DISABLE_FIND_PACKAGE_rosidl_generator_rs=TRUE：禁用此次不需要的 Rust 消息生成器。
# CMAKE_C_COMPILER / CMAKE_CXX_COMPILER：明确选择干净 GCC 11 的 C/C++ 编译器。
# CMAKE_SYSROOT：编译和链接使用干净开发文件，最终运行无需这个 RAM 目录。
# CMAKE_FIND_ROOT_PATH_MODE_PACKAGE=NEVER：包查找仍使用真实的独立安装前缀。
# CMAKE_C_FLAGS：最多报告两个错误，并加入私有 NumPy 的 C 头文件目录。
# CMAKE_CXX_FLAGS：最多报告两个错误，并加入私有 Ubuntu 的开发头文件目录。
# console_bridge_DIR：直接指定私有 console_bridge 的 CMake 配置目录。
# PYTHON_INCLUDE_DIR：指定干净 Python 3.10 开发头文件。
# LIVOX_LIDAR_SDK_INCLUDE_DIR / LIBRARY：指定单独构建的 SDK 头文件和共享库。
# 最后的 2>&1 合并错误输出，tee 同时显示并保存编译日志。
colcon --log-base "$task_root/log-clean" build \
  --base-paths "$task_root/src/livox_ros_driver2" \
  --build-base "$task_root/build-clean" --install-base "$runtime_root/install" \
  --cmake-args -DROS_EDITION=ROS2 -DDISTRO_ROS=humble \
  -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF \
  -DAMENT_CMAKE_SYMLINK_INSTALL=OFF \
  -DCMAKE_DISABLE_FIND_PACKAGE_rosidl_generator_rs=TRUE \
  -DCMAKE_C_COMPILER="$toolchain_root/usr/bin/aarch64-linux-gnu-gcc-11" \
  -DCMAKE_CXX_COMPILER="$toolchain_root/usr/bin/aarch64-linux-gnu-g++-11" \
  -DCMAKE_SYSROOT="$toolchain_root" \
  -DCMAKE_FIND_ROOT_PATH_MODE_PACKAGE=NEVER \
  -DCMAKE_C_FLAGS="-fmax-errors=2 -I$runtime_root/ubuntu-clean/usr/lib/python3/dist-packages/numpy/core/include" \
  -DCMAKE_CXX_FLAGS="-fmax-errors=2 -I$runtime_root/ubuntu-clean/usr/include" \
  -Dconsole_bridge_DIR="$runtime_root/ubuntu-clean/usr/lib/aarch64-linux-gnu/console_bridge/cmake" \
  -DPYTHON_INCLUDE_DIR="$toolchain_root/usr/include/python3.10" \
  -DLIVOX_LIDAR_SDK_INCLUDE_DIR="$runtime_root/sdk/include" \
  -DLIVOX_LIDAR_SDK_LIBRARY="$runtime_root/sdk/lib/liblivox_lidar_sdk_shared.so" \
  2>&1 | tee "$task_root/build-clean-output.log"
