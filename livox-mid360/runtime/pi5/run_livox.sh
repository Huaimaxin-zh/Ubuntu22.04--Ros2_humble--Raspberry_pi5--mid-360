#!/usr/bin/env bash
# 启动真实MID360驱动；没有Viewer/RViz窗口，点云保留FAST-LIO所需CustomMsg。
set -eo pipefail
source /home/xin/livox_runtime/env.sh
# 先检查本机接收地址，再检查实际物理链路，避免空启动后误认为设备正常。
ip -4 address show dev eth0 | grep -q '192.168.123.4/24' || {
    echo 'eth0缺少192.168.123.4/24，请检查05-livox-eth0.network。' >&2; exit 1;
}
[[ $(cat /sys/class/net/eth0/carrier) == 1 ]] || {
    echo 'eth0没有物理链路，请检查雷达供电与网线。' >&2; exit 1;
}
cd /home/xin/livox_runtime
exec ros2 launch livox_ros_driver2 msg_MID360_launch.py
