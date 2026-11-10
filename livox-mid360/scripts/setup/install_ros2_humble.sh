#!/usr/bin/env bash
# 用途：在 Ubuntu 22.04 ARM64 树莓派上安装 ROS2 Humble 基础开发环境。
# 执行位置：树莓派的 VS Code Remote-SSH 终端；需要 sudo。
# 不做全系统升级；不改网络配置、分区、内核或固件。
# 所有安装记录保存在 /home/xin/pi_setup，失败时会停止并写入状态文件。

# -e：命令失败停止；-u：禁止未定义变量；pipefail：检查管道中每一步。
set -Eeuo pipefail

# 固定本次配置目录，避免误用其他用户的文件。
setup_dir=/home/xin/pi_setup
# 文件名中的 UTC 时间用于保留多次运行的独立记录。
run_id=$(date -u +%Y%m%dT%H%M%SZ)
# 日志保存在普通用户可读取的位置。
log_file="$setup_dir/install-$run_id.log"

# 系统包安装必须由 root 执行；脚本不会索取或保存密码。
if [[ $EUID -ne 0 ]]; then
    printf '请执行：sudo bash /home/xin/pi_setup/install_ros2_humble.sh\n' >&2
    exit 1
fi

# 防止两个安装会话同时运行。
exec 9>/run/pi-ros2-setup.lock
flock -n 9 || { printf '已有 ROS2 安装会话在运行。\n' >&2; exit 1; }

# tee 同时显示进度并保存日志；不修改终端中的密码输入方式。
exec > >(tee -a "$log_file") 2>&1
# 状态文件让远程检查可以判断安装是否结束。
printf 'RUNNING %s\n' "$run_id" > "$setup_dir/install.status"
# 无论成功或失败，都记录真实退出码。
finish() {
    result=$?
    trap - EXIT
    printf '\nINSTALL_EXIT=%s\n' "$result"
    printf 'EXIT=%s LOG=%s\n' "$result" "$log_file" > "$setup_dir/install.status"
    chmod 644 "$log_file" "$setup_dir/install.status"
    exit "$result"
}
trap finish EXIT

# 从发行版提供的文件读取系统信息。
source /etc/os-release
# 只接受本次确认的 Ubuntu Jammy 与 arm64，防止套错安装方案。
[[ $ID == ubuntu && $VERSION_CODENAME == jammy ]]
[[ $(dpkg --print-architecture) == arm64 ]]
# UTF-8 是 ROS2 的运行要求；本卡已有 C.UTF-8，无需改全局语言。
export LANG=C.UTF-8
export LC_ALL=C.UTF-8

printf '\n=== 系统与存储只读检查 ===\n'
uname -a
findmnt -no SOURCE,FSTYPE,OPTIONS /
df -h /
# 至少保留 6 GiB 可用空间才继续安装。
available_bytes=$(df -B1 --output=avail / | tail -n 1)
(( available_bytes > 6 * 1024 * 1024 * 1024 ))
# 数据库必须健康；不会自动删除或重建 dpkg 数据库。
audit_output=$(dpkg --audit)
if [[ -n $audit_output ]]; then
    printf '%s\n' "$audit_output"
    printf 'dpkg 有未完成状态，已停止安装。\n' >&2
    exit 1
fi
# 保存本次开机的内核日志，供检查 SD 卡或供电异常使用。
journalctl -k -b --no-pager > "$setup_dir/kernel-before-$run_id.log"

printf '\n=== 备份软件源配置 ===\n'
backup_dir="$setup_dir/backups/$run_id"
mkdir -p "$backup_dir"
cp -a /etc/apt "$backup_dir/apt"

printf '\n=== 校验官方 ROS2 源管理包 ===\n'
source_package="$setup_dir/ros2-apt-source_1.3.0.jammy_all.deb"
# SHA256 来自 ROS 官方 GitHub release 的资产元数据。
printf '%s  %s\n' \
    110b9a462d55252decb8b7c816f61c2ba0d9890ce5fb93ac504e97cae5860d76 \
    "$source_package" | sha256sum --check -
# 检查包名、版本、架构；不接受其他软件包冒充该文件。
[[ $(dpkg-deb -f "$source_package" Package) == ros2-apt-source ]]
[[ $(dpkg-deb -f "$source_package" Architecture) == all ]]
dpkg-deb --info "$source_package"
# 该官方包管理 ROS2 软件源和签名密钥。
dpkg -i "$source_package"

# 仅对当前脚本生效：不弹出服务重启选择，不改用户默认环境。
export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=l
# 网络超时和重试参数使连接失败时有明确结果。
apt_options=(-o Acquire::Retries=3 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30)

printf '\n=== 更新签名软件索引 ===\n'
# 任一源更新失败就停止，避免拿不完整索引继续安装。
apt-get "${apt_options[@]}" -o APT::Update::Error-Mode=any update

# 无桌面基础版，加 C++/Python 通信示例和常用开发工具。
packages=(
    ros-humble-ros-base
    ros-humble-demo-nodes-cpp
    ros-humble-demo-nodes-py
    python3-colcon-common-extensions
    python3-rosdep
    python3-vcstool
    build-essential
    cmake
    git
    curl
    ca-certificates
)

printf '\n=== 模拟安装并检查包变更 ===\n'
plan_file="$setup_dir/apt-plan-$run_id.log"
apt-get "${apt_options[@]}" -s --no-remove --no-install-recommends \
    install "${packages[@]}" | tee "$plan_file"
# 本次安装不允许删除现有包，也不允许触及 Pi 的内核与固件包。
if grep -Eq '^Remv |^Inst (linux-image|linux-headers|linux-modules|linux-raspi|linux-firmware|raspi-firmware|raspberrypi|rpi-eeprom|flash-kernel)' "$plan_file"; then
    printf '安装计划涉及系统包删除、内核或固件，已停止。\n' >&2
    exit 1
fi

printf '\n=== 正式安装 ROS2 与开发工具 ===\n'
# --no-remove 禁止为解决依赖而删除包；保留已有配置文件。
apt-get "${apt_options[@]}" -y --no-remove --no-install-recommends \
    -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold \
    install "${packages[@]}"

printf '\n=== 检查安装状态 ===\n'
dpkg --audit
dpkg-query -W ros-humble-ros-base ros-humble-demo-nodes-cpp \
    ros-humble-demo-nodes-py python3-colcon-common-extensions python3-rosdep git
test -r /opt/ros/humble/setup.bash
# 保存安装后的版本信息，便于后续复现和排查。
dpkg-query -W > "$setup_dir/packages-after-$run_id.tsv"
# 初始化依赖规则来源；下载与缓存更新稍后以 xin 普通用户运行。
if [[ ! -e /etc/ros/rosdep/sources.list.d/20-default.list ]]; then
    # raw.githubusercontent.com 当前需要经电脑已有的代理访问。
    # 此代理环境只给本次 rosdep 命令使用，不改系统或 APT 代理。
    http_proxy=http://192.168.0.101:7897 \
    https_proxy=http://192.168.0.101:7897 \
    HTTP_PROXY=http://192.168.0.101:7897 \
    HTTPS_PROXY=http://192.168.0.101:7897 rosdep init
fi
printf '\nROS2 系统包安装完成；随后由远程会话完成用户环境与通信验证。\n'
