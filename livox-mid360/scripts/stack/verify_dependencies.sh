#!/usr/bin/env bash
# 普通用户复核已安装依赖；不会重新安装软件或改动系统配置。
# 本次首次安装后的检查误用了pcl_common名称，原始失败日志保留供追溯。
set -eo pipefail
setup_dir=/home/xin/livox_stack_setup
exec > >(tee "$setup_dir/verify-dependencies.log") 2>&1
printf 'RUNNING\n' > "$setup_dir/dependencies-verified.status"
trap 'result=$?; printf "EXIT=%s\n" "$result" > "$setup_dir/dependencies-verified.status"' EXIT
audit_output=$(dpkg --audit)
[[ -z $audit_output ]] || { printf '%s\n' "$audit_output"; exit 1; }
# 检查实际安装状态，而不是仅判断文件名存在。
for package in libpcl-dev libapr1-dev libeigen3-dev ros-humble-pcl-conversions ros-humble-pcl-ros; do
    test "$(dpkg-query -W -f='${Status}' "$package")" = 'install ok installed'
    dpkg-query -W "$package"
done
# Jammy的PCL .pc文件采用带版本号的模块名称。
if pkg-config --exists pcl_common; then
    pcl_module=pcl_common
else
    pcl_module=pcl_common-1.12
fi
pkg-config --modversion "$pcl_module" apr-1 eigen3
test -r /usr/lib/aarch64-linux-gnu/cmake/pcl/PCLConfig.cmake
echo 'DEPENDENCIES_VERIFIED_OK'
