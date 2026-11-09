#!/usr/bin/env bash
# 上一行说明使用环境中的 Bash；也可以显式执行 bash run_livox.sh。

# 普通命令执行失败时停止，避免在环境加载失败后继续启动驱动。
set -e

# 已安装运行环境的位置；脚本从这里读取环境、配置和可执行文件。
root=/home/xin/livox_runtime

# 在本脚本进程中加载独立环境，不要求用户手动 source。
source "$root/env.sh"

# ip 显示 eth0 的 IPv4 地址；grep -q 只检查是否存在指定地址而不打印。
# ! 对检查结果取反：如果没有 192.168.123.4/24，就执行下面的提示。
if ! ip -o -4 addr show eth0 | grep -q 'inet 192.168.123.4/24'; then
  # >&2 把提示写到标准错误，方便与正常输出区分。
  echo 'eth0 needs 192.168.123.4/24. Run:' >&2
  # 这里只打印建议命令，并没有替用户执行 sudo 或修改网络。
  echo 'sudo ip link set eth0 up' >&2
  echo 'sudo ip address replace 192.168.123.4/24 dev eth0' >&2
  # 非零退出码表示检查未通过；2 是本脚本选择的配置错误代码。
  exit 2
fi

# carrier=1 表示有物理链路；读不到或不等于 1 时停止。
# 2>/dev/null 仅隐藏读取 carrier 时的系统错误，不会改写该文件。
if test "$(cat /sys/class/net/eth0/carrier 2>/dev/null)" != 1; then
  echo 'eth0 has no physical link. Check MID360 power and its Ethernet cable.' >&2
  exit 2
fi

# exec 用官方编译出的驱动进程替换当前脚本，Ctrl+C 可直接传给驱动。
# 下面各行末尾的反斜杠表示同一条命令换行书写。
# 参数说明见 docs/05-script-explanation.md；末尾 "$@" 保留调用者追加的参数。
exec "$root/install/livox_ros_driver2/lib/livox_ros_driver2/livox_ros_driver2_node" \
  --ros-args -r __node:=livox_lidar_publisher \
  -p xfer_format:=1 -p multi_topic:=0 -p data_src:=0 \
  -p publish_freq:=10.0 -p output_data_type:=0 -p frame_id:=livox_frame \
  -p user_config_path:="$root/config/MID360_config.json" "$@"
