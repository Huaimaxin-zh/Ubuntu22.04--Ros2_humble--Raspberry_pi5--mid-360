#!/usr/bin/env bash
# 用法：bash ~/livox_runtime/run_fastlio.sh [--save-map]
# 先在另一终端启动驱动；初始化时静止放置雷达数秒。
set -eo pipefail
source /home/xin/livox_runtime/env.sh
config_file=mid360_pi5.yaml
if [[ ${1:-} == --save-map ]]; then
    # 保存模式会缓存整图，供短时采集并调用/map_save使用。
    config_file=mid360_pi5_save.yaml
    echo '短时保存模式：建议60-120秒后停止，避免整图缓存持续增长。'
elif [[ $# -gt 0 ]]; then
    echo '用法：run_fastlio.sh [--save-map]' >&2
    exit 1
fi
cd /home/xin/livox_runtime
# 显式rviz:=false，不要求树莓派有桌面或图形软件。
exec ros2 launch fast_lio mapping.launch.py \
    config_path:=/home/xin/livox_runtime/config config_file:="$config_file" \
    rviz:=false use_sim_time:=false
