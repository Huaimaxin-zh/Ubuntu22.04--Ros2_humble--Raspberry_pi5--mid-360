#!/usr/bin/env bash
# 按顺序编译驱动与FAST-LIO：FAST-LIO需要先加载驱动的自定义消息包。
# 在xin普通用户下执行，无需sudo；两个独立工作空间避免互相清理产物。
set -eo pipefail
setup_dir=/home/xin/livox_stack_setup
exec > >(tee "$setup_dir/build-ros-stack.log") 2>&1
printf 'RUNNING\n' > "$setup_dir/ros-stack.status"
trap 'result=$?; printf "EXIT=%s\n" "$result" > "$setup_dir/ros-stack.status"' EXIT
source /opt/ros/humble/setup.bash
# SDK安装在用户目录，运行和构建都显式指定它的位置。
export LD_LIBRARY_PATH="/home/xin/livox_sdk2/lib:${LD_LIBRARY_PATH:-}"
export CMAKE_BUILD_PARALLEL_LEVEL=1 MAKEFLAGS=-j1

printf '\n=== livox_ros_driver2 ===\n'
cd /home/xin/ws_livox
colcon build --packages-select livox_ros_driver2 --symlink-install \
    --executor sequential --cmake-args -DROS_EDITION=ROS2 -DDISTRO_ROS=humble \
    -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF \
    -DCMAKE_DISABLE_FIND_PACKAGE_rosidl_generator_rs=TRUE \
    -DLIVOX_LIDAR_SDK_INCLUDE_DIR=/home/xin/livox_sdk2/include \
    -DLIVOX_LIDAR_SDK_LIBRARY=/home/xin/livox_sdk2/lib/liblivox_lidar_sdk_shared.so
# 此层提供 livox_ros_driver2/msg/CustomMsg，供 FAST-LIO 编译与运行使用。
source /home/xin/ws_livox/install/setup.bash
ros2 interface show livox_ros_driver2/msg/CustomMsg

printf '\n=== FAST-LIO ===\n'
cd /home/xin/ws_fastlio
# 本卡4GB/无swap，首次-O2编译laserMapping.cpp时编译器被终止。
# 使用-O1并让GCC更频繁回收编译器内部内存，避免修改系统swap或内核设置。
# 运行时性能需在实机接入后测量；不能凭编译通过承诺10Hz建图性能。
colcon build --packages-select fast_lio --symlink-install \
    --executor sequential --cmake-args -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_CXX_FLAGS_RELEASE='-O1 -DNDEBUG --param=ggc-min-expand=10 --param=ggc-min-heapsize=32768' \
    -DBUILD_TESTING=OFF \
    -DCMAKE_DISABLE_FIND_PACKAGE_rosidl_generator_rs=TRUE
source /home/xin/ws_fastlio/install/setup.bash
ros2 pkg executables livox_ros_driver2
ros2 pkg executables fast_lio
echo 'ROS_STACK_BUILD_OK'
