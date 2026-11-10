#!/usr/bin/env bash
# 用途：安装 MID360 驱动和 FAST-LIO 的系统依赖，并设置雷达专用 eth0。
# 执行位置：树莓派 VS Code Remote-SSH 终端，需要本地输入 sudo 密码。
# 只给 eth0 配静态地址，不配置网关/DNS，不重启 Wi-Fi 或整套网络服务。
set -Eeuo pipefail
[[ $EUID -eq 0 ]] || { echo '请使用 sudo bash 执行本脚本。' >&2; exit 1; }
source /etc/os-release
[[ $ID == ubuntu && $VERSION_CODENAME == jammy ]]
[[ $(dpkg --print-architecture) == arm64 ]]

# 本次脚本和日志集中保存；时间戳防止覆盖旧记录。
setup_dir=/home/xin/livox_stack_setup
run_id=$(date -u +%Y%m%dT%H%M%SZ)
log_file="$setup_dir/dependencies-$run_id.log"
exec 9>/run/livox-stack-dependencies.lock
flock -n 9 || { echo '依赖安装已经在运行。' >&2; exit 1; }
exec > >(tee -a "$log_file") 2>&1
printf 'RUNNING %s\n' "$run_id" > "$setup_dir/dependencies.status"
finish() {
    result=$?
    trap - EXIT
    printf '\nDEPENDENCIES_EXIT=%s\n' "$result"
    printf 'EXIT=%s LOG=%s\n' "$result" "$log_file" > "$setup_dir/dependencies.status"
    chmod 644 "$log_file" "$setup_dir/dependencies.status"
    exit "$result"
}
trap finish EXIT
export DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l
export LANG=C.UTF-8 LC_ALL=C.UTF-8

# dpkg 数据库必须健康；本次不会删除、重建数据库或修改 SD 卡分区。
audit_output=$(dpkg --audit)
[[ -z $audit_output ]] || { printf '%s\n' "$audit_output"; exit 1; }
df -h /
available_bytes=$(df -B1 --output=avail / | tail -n 1)
(( available_bytes > 8 * 1024 * 1024 * 1024 ))
backup_dir="$setup_dir/backups/$run_id"
mkdir -p "$backup_dir"

printf '\n=== 配置雷达专用网口 ===\n'
# systemd-networkd 按文件名顺序选第一个匹配接口的配置。
# 此文件只匹配 eth0，不接管 wlan0。
network_file=/etc/systemd/network/05-livox-eth0.network
[[ ! -e $network_file ]] || cp -a "$network_file" "$backup_dir/"
cat > "$network_file" <<'NETWORK'
# MID360 数据接收网口。无线网络继续负责上网和 SSH。
[Match]
Name=eth0

[Link]
RequiredForOnline=no

[Network]
Address=192.168.123.4/24
DHCP=no
LinkLocalAddressing=no
IPv6AcceptRA=no
NETWORK
chmod 644 "$network_file"
# reload 只重读文件，reconfigure 只对 eth0 应用配置。
networkctl reload
ip link set eth0 up
networkctl reconfigure eth0
# replace 确保本次立即可用；不删除其他接口的地址。
ip address replace 192.168.123.4/24 dev eth0
ip -br -4 addr show eth0
# ping 失败不会中断依赖安装，物理接线可在编译期间完成。
ping -c 3 -W 2 192.168.123.20 || true

printf '\n=== 更新签名软件包索引 ===\n'
apt_options=(-o Acquire::Retries=3 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30)
apt-get "${apt_options[@]}" -o APT::Update::Error-Mode=any update

# SDK2 使用系统编译工具；driver 和 FAST-LIO 需要 PCL、Eigen、APR 及 ROS 转换库。
packages=(
    libpcl-dev libeigen3-dev libapr1-dev pkg-config
    ros-humble-pcl-conversions ros-humble-pcl-ros
    ros-humble-visualization-msgs ros-humble-std-srvs
    python3-dev python3-numpy
)
printf '\n=== 模拟并核对依赖变更 ===\n'
plan_file="$setup_dir/apt-plan-$run_id.log"
apt-get "${apt_options[@]}" -s --no-remove --no-install-recommends \
    install "${packages[@]}" | tee "$plan_file"
# 不允许为安装依赖而移除已有软件，也不允许修改内核与固件包。
if grep -Eq '^Remv |^Inst (linux-image|linux-headers|linux-modules|linux-raspi|linux-firmware|raspi-firmware|raspberrypi|rpi-eeprom|flash-kernel)' "$plan_file"; then
    echo '计划包含软件删除、内核或固件变更，停止安装。' >&2
    exit 1
fi

printf '\n=== 安装依赖 ===\n'
apt-get "${apt_options[@]}" -y --no-remove --no-install-recommends \
    -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold \
    install "${packages[@]}"

printf '\n=== 验证依赖状态 ===\n'
audit_output=$(dpkg --audit)
[[ -z $audit_output ]] || { printf '%s\n' "$audit_output"; exit 1; }
# Ubuntu Jammy 的 PCL pkg-config 名称带 -1.12；兼容其他发行包的不带版本名称。
if pkg-config --exists pcl_common; then
    pcl_module=pcl_common
else
    pcl_module=pcl_common-1.12
fi
pkg-config --modversion "$pcl_module" apr-1 eigen3
dpkg-query -W "${packages[@]}"
journalctl -k -b --no-pager > "$setup_dir/kernel-after-dependencies-$run_id.log"
echo '系统依赖安装完成。后续 SDK/ROS 源码编译以 xin 普通用户执行。'
