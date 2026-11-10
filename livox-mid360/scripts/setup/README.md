# 新卡 ROS2 Humble / Git 配置脚本留档

这些文件是 2026-11-10 在新 SD 卡上实际使用并通过验收的脚本与测试源码，逐步说明见 [配置记录](../../docs/09-ros2-git-new-card-setup.md)。它们使用 `/home/xin/pi_setup` 作为部署目录，适用于本次 Ubuntu 22.04 ARM64、用户 `xin` 的树莓派5。更换用户名、网络或系统版本后，应先阅读和调整路径。

| 文件 | 用途 |
| --- | --- |
| `install_ros2_humble.sh` | 系统检查、源配置备份、官方源管理包校验、APT 模拟及实际安装、rosdep 初始化 |
| `configure_user.py` | 备份 `.bashrc`，追加环境加载语句，建立开发源码目录 |
| `ros2_env.bash` | 新 Bash 终端加载 ROS2 Humble 基础环境 |
| `verify_setup.sh` | 普通用户执行依赖检查、节点通信、colcon 实际构建及 Git 完整性检查 |
| `verify_ros2_runtime.py` | 实际运行官方 C++ 发布者与 Python 订阅者，要求收到至少五条消息 |
| `verification_ws/src/pi_setup_smoke_cpp` | 最小 C++ 验证包；源码、包依赖和 CMake 文件均有中文注释 |

脚本仅加载 ROS2 基础环境，后续雷达与建图工作空间需分别编译和验证。测试的 Domain 为 `177`，限定本机通信；它不会验证跨机器通信。

## 在同类新卡复现时如何准备

以下是部署说明，不需要在已安装成功的树莓派重复执行。先阅读所有脚本，再按实际设备准备；脚本中的电脑代理为 `192.168.0.101:7897`，地址变化时需调整。

```bash
# 在树莓派普通用户终端创建本次脚本约定的部署目录。
mkdir -p ~/pi_setup

# 从仓库复制明确列出的脚本，保留已有其他文件。
cp ~/projects/raspberrypi-mid360/livox-mid360/scripts/setup/install_ros2_humble.sh ~/pi_setup/
cp ~/projects/raspberrypi-mid360/livox-mid360/scripts/setup/configure_user.py ~/pi_setup/
cp ~/projects/raspberrypi-mid360/livox-mid360/scripts/setup/ros2_env.bash ~/pi_setup/
cp ~/projects/raspberrypi-mid360/livox-mid360/scripts/setup/verify_setup.sh ~/pi_setup/
cp ~/projects/raspberrypi-mid360/livox-mid360/scripts/setup/verify_ros2_runtime.py ~/pi_setup/

# 复制的只有验证包源码，不包含 build/install/log。
cp -r ~/projects/raspberrypi-mid360/livox-mid360/scripts/setup/verification_ws ~/pi_setup/
```

安装脚本需要预先放好官方源管理包；仓库不存储 `.deb` 二进制：

```bash
# 从 ROS 官方 release 下载本次已验证的 Jammy 包。
curl -fL --retry 3 \
  https://github.com/ros-infrastructure/ros-apt-source/releases/download/1.3.0/ros2-apt-source_1.3.0.jammy_all.deb \
  -o ~/pi_setup/ros2-apt-source_1.3.0.jammy_all.deb

# 核对下载内容；应显示 OK，失败则停止。
printf '%s  %s\n' \
  110b9a462d55252decb8b7c816f61c2ba0d9890ce5fb93ac504e97cae5860d76 \
  "$HOME/pi_setup/ros2-apt-source_1.3.0.jammy_all.deb" | sha256sum --check -
```

只有确实需要在新系统安装时，才执行：

```bash
# 普通用户：设置 Bash 加载规则；会备份已有 .bashrc。
python3 ~/pi_setup/configure_user.py

# 管理员步骤：安装系统包；密码只在树莓派终端输入。
sudo bash ~/pi_setup/install_ros2_humble.sh

# 安装成功后，以普通用户验收，不使用 sudo。
bash ~/pi_setup/verify_setup.sh
```

脚本日志中的时间戳使用 UTC 以便机器排序，本文日期使用北京时间。系统安装和验收成功分别由 `~/pi_setup/install.status`、`~/pi_setup/verification/status` 中的 `EXIT=0` 表示；验收日志还需包含 `ALL_SETUP_CHECKS_PASSED=true`。

Git 提交身份和 GitHub 登录独立配置，具体见 [Git 配置记录](../../docs/09-ros2-git-new-card-setup.md#在-vs-code-中管理代码)。本次没有把任何 SSH 私钥、GitHub 凭据、系统备份、软件包或构建产物放入此目录。
