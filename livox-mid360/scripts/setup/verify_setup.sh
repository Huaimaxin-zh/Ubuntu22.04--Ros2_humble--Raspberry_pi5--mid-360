#!/usr/bin/env bash
# 用途：由 xin 普通用户验收本次安装；不要使用 sudo 执行。
# 所有构建和测试只发生在 pi_setup 的独立验证目录内。
set -eo pipefail

# 确保加载已安装的 ROS2，而不是旧卡遗留的用户运行环境。
source /opt/ros/humble/setup.bash
# 保存验收日志，终端仍会实时显示。
mkdir -p /home/xin/pi_setup/verification
exec > >(tee /home/xin/pi_setup/verification/verify-setup.log) 2>&1
printf 'RUNNING\n' > /home/xin/pi_setup/verification/status
# 无论成功失败都留下退出码。
trap 'result=$?; printf "EXIT=%s\n" "$result" > /home/xin/pi_setup/verification/status' EXIT

printf '\n=== 软件包完整状态 ===\n'
# dpkg --audit 有时只打印异常，因此必须检查输出为空。
audit_output=$(dpkg --audit)
[[ -z $audit_output ]] || { printf '%s\n' "$audit_output"; exit 1; }
printf 'DPKG_AUDIT_EMPTY=true\n'
printf 'ROS_DISTRO=%s\n' "$ROS_DISTRO"
command -v ros2
# rclpy 是 Python 库，rclcpp 是 C++ 库；只导入应有的 Python 库。
python3 -c 'import rclpy; from std_msgs.msg import String; print("PYTHON_ROS_IMPORT_OK")'

printf '\n=== 普通用户 rosdep 缓存 ===\n'
# GitHub raw 内容需经过现有电脑代理，仅给当前命令使用。
http_proxy=http://192.168.0.101:7897 \
https_proxy=http://192.168.0.101:7897 \
HTTP_PROXY=http://192.168.0.101:7897 \
HTTPS_PROXY=http://192.168.0.101:7897 rosdep update --rosdistro humble

printf '\n=== C++ 发布者到 Python 订阅者 ===\n'
python3 /home/xin/pi_setup/verify_ros2_runtime.py

printf '\n=== colcon 选包与实际 C++ 编译 ===\n'
cd /home/xin/pi_setup/verification_ws
# check 会核对 package.xml 声明的依赖是否已安装。
rosdep check --from-paths src --ignore-src --rosdistro humble
# 单线程既验证 --packages-select 插件，也避免树莓派内存峰值过高。
CMAKE_BUILD_PARALLEL_LEVEL=1 MAKEFLAGS=-j1 \
    colcon build --packages-select pi_setup_smoke_cpp --symlink-install \
    --executor sequential --cmake-args -DCMAKE_BUILD_TYPE=Release
# 编译成功后加载这个独立工作空间，以便 ros2 run 找到测试包。
source install/setup.bash
# 测试节点在独立 Domain、本机范围运行，结束后不会常驻后台。
ROS_DOMAIN_ID=177 ROS_LOCALHOST_ONLY=1 \
    ros2 run pi_setup_smoke_cpp setup_check

printf '\n=== Git 仓库检查 ===\n'
git -C /home/xin/projects/raspberrypi-mid360 fsck --full
git -C /home/xin/projects/raspberrypi-mid360 status --short --branch
git -C /home/xin/projects/raspberrypi-mid360 log -1 --oneline
printf '\nALL_SETUP_CHECKS_PASSED=true\n'
