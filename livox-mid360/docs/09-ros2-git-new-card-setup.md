# 树莓派5：ROS2 Humble 与 Git 配置记录

记录日期：2026-11-10。本文中的命令均在 **VS Code Remote-SSH 已连接的树莓派终端**执行，用户名为 `xin`；不要在 Windows PowerShell 或 Ubuntu 虚拟机终端照搬运行。

本记录对应用户重新烧录的新 SD 卡。旧卡维修的结论仍以 [SD 卡维修记录](07-sd-card-recovery-report.md) 为准，不能用新卡安装成功证明旧卡已经修复。带中文注释的脚本已归档在 [scripts/setup](../scripts/setup/README.md)，精选验收结果见 [JSON](../evidence/2026-11-10-ros2-git-new-card-setup.json)。

## 当前状态

| 项目 | 配置与验收情况 |
|---|---|
| 设备与系统 | 树莓派5，Ubuntu 22.04.5，ARM64（`aarch64`），用户 `xin` |
| ROS2 | 已安装 Humble 基础版 `ros-humble-ros-base`、C++/Python 演示节点及开发工具；安装退出码 0 |
| ROS2 通信 | C++ 发布者 → Python 订阅者连续接收 5 条 `Hello World` 消息，通过 |
| ROS2 编译 | `colcon --packages-select` 单线程构建 C++ 示例成功，运行打印 `PI5_HUMBLE_CPP_BUILD_OK` |
| 依赖工具 | rosdep 已初始化，xin 用户的 Humble 缓存更新成功；示例依赖检查通过 |
| 软件包状态 | `dpkg --audit` 输出为空；整体验收退出码 0 |
| 新终端环境 | 新 Bash 自动加载后输出 `ROS_DISTRO=humble`、`ROS_VERSION=2` |
| Git | 已安装，提交身份沿用 Windows 现有仓库：`huaimaxin <3339590580@qq.com>` |
| 项目目录 | `/home/xin/projects/raspberrypi-mid360` |
| 当前分支 | `docs/livox-setup`，保留已有仓库历史 |
| GitHub 获取 | 已成功执行 `fetch` |
| GitHub 推送检查 | 用户在 VS Code 中执行 `push --dry-run`，返回 `Everything up-to-date`；该检查没有上传新提交 |
| 雷达与建图 | 本次尚未配置或测试 Livox 驱动、FAST-LIO |

ROS2 安装采用官方 `ros2-apt-source` 1.3.0 管理软件源与签名密钥，已安装基础版、演示节点、`colcon` 常用插件、`rosdep`、`vcstool`、CMake 和 C++ 编译工具。官方源管理包的 SHA256 已与 release 资产元数据核对。安装前模拟依赖，实际新增 376 个软件包、更新 17 个依赖包，删除 0 个包；内核仍为 `6.8.0-1047-raspi`。安装后根分区约有 23 GB 可用空间。

ROS2 基础环境与开发工具已经验收；此次通信测试限定在树莓派本机，跨电脑通信和雷达数据链路需要在后续接入设备时单独验证。

## ROS2 环境与目录

`~/.bashrc` 已加入加载 `/home/xin/pi_setup/ros2_env.bash` 的语句。该文件会在基础安装存在时加载 `/opt/ros/humble/setup.bash`，不会提前加载尚未编译的工作空间。

```bash
# 当前已经打开的终端：ROS2 安装完成后，手动加载一次基础环境。
source /opt/ros/humble/setup.bash

# 查看当前终端选择的 ROS2 发行版；预期输出 humble。
echo "$ROS_DISTRO"

# 查看 ROS2 命令路径；预期位于 /opt/ros/humble/bin/ros2。
command -v ros2
```

安装完成后新开的 Bash 终端会自动加载基础环境。VS Code 编辑代码本身不要求重新加载；编译产生新包后，运行前需要加载相应工作空间。

已创建两个源码目录：

- `/home/xin/dev_ws/src`：通用 ROS2 学习与开发源码。
- `/home/xin/ws_livox/src`：预留给后续 Livox 驱动等源码。

下面是未来加入功能包后的构建方式；空工作空间不能据此证明驱动已经可用。

```bash
# 进入工作空间根目录；不要在 src 子目录中编译。
cd ~/dev_ws

# 低并行编译，适合树莓派有限内存；实际依赖应先安装齐全。
CMAKE_BUILD_PARALLEL_LEVEL=1 MAKEFLAGS=-j1 colcon build --symlink-install --executor sequential

# 仅在上一步编译成功后，加载本工作空间的安装结果。
source ~/dev_ws/install/setup.bash
```

## 在 VS Code 中管理代码

在 VS Code 的“文件 → 打开文件夹”中打开 `/home/xin/projects/raspberrypi-mid360`，即可使用左侧“源代码管理”查看差异。也可使用下面的命令；`git -C` 明确指定仓库，因而不依赖终端当前所在目录。

```bash
# 查看当前分支、暂存内容及尚未提交的修改；不改变文件。
git -C ~/projects/raspberrypi-mid360 status

# 查看最近五次提交；不改变历史。
git -C ~/projects/raspberrypi-mid360 log -5 --oneline

# 下载远程分支的最新记录；不会自动合并或覆盖工作区。
git -C ~/projects/raspberrypi-mid360 fetch --prune origin

# 在确认工作区状态后，以只允许快进的方式更新当前分支。
git -C ~/projects/raspberrypi-mid360 pull --ff-only

# 推送权限预检查；不上传提交。
git -C ~/projects/raspberrypi-mid360 push --dry-run origin HEAD:docs/livox-setup
```

**修改或保存文件不会自动创建 Git 提交，也不会自动上传 GitHub。** 提交时先检查差异，再只暂存本次需要保存的文件。下面使用 `docs/example.md` 示意，操作时应改成实际存在的文件路径。

```bash
# 查看尚未暂存的内容差异。
git -C ~/projects/raspberrypi-mid360 diff

# 只暂存指定文档；应先把示例路径改成实际文件。
git -C ~/projects/raspberrypi-mid360 add -- docs/example.md

# 复查即将写入提交的具体内容。
git -C ~/projects/raspberrypi-mid360 diff --cached

# 创建本地提交；此时尚未上传 GitHub。
git -C ~/projects/raspberrypi-mid360 commit -m "docs: record configuration changes"

# 将已经检查过的提交上传到现有资料分支。
git -C ~/projects/raspberrypi-mid360 push origin HEAD:docs/livox-setup
```

不要提交私钥、密码、令牌、`authorized_keys`、雷达原始数据、PCD 地图、SD 卡镜像，以及 `build/`、`install/`、`log/` 等构建产物。现有仓库的 `.gitignore` 已覆盖常见内容，但每次提交前仍需查看暂存差异。

## GitHub 网络代理

树莓派直接连接 GitHub 曾超时，现已为 **Git 访问 `https://github.com/`** 配置电脑现有代理：`http://192.168.0.101:7897`。它不是整台树莓派的系统代理，也不会代理 ROS2/DDS 或雷达 UDP 数据。

```bash
# 只读查看 GitHub 专用代理设置。
git config --global --get http.https://github.com/.proxy

# 电脑 IP 或代理端口改变时，按实际地址修改此设置。
git config --global http.https://github.com/.proxy http://192.168.0.101:7897

# 以后确认树莓派可直连 GitHub 时，移除这条代理配置。
git config --global --unset http.https://github.com/.proxy
```

使用该代理时，电脑需要开机、与树莓派网络互通，并保持对应代理可用。Git 提交身份与 GitHub 登录是不同事项；本次推送预检查已在 VS Code 会话中通过，不代表向树莓派复制了 Windows 的私人密钥。

## 日志与备份

本次配置文件、脚本、安装记录、原 `.bashrc` 备份及验证文件均放在 `/home/xin/pi_setup`。安装日志名类似 `install-20261110T024132Z.log`，安装状态文件为 `install.status`。

```bash
# 查看本次安装是否仍在运行，以及最终退出码和日志路径。
cat ~/pi_setup/install.status

# 列出本次配置记录；不修改文件。
ls -lh ~/pi_setup

# 检查是否还有安装未完成的软件包；健康状态通常无输出。
dpkg --audit
```

验收结果保存在 `~/pi_setup/verification/verify-setup.log`，末尾为 `ALL_SETUP_CHECKS_PASSED=true`。测试 C++ 包源码在 `~/pi_setup/verification_ws/src/pi_setup_smoke_cpp`；源码和验证脚本均带有中文注释。

可在需要时重新运行本次验收（会重新生成测试日志并进行一次增量构建）：

```bash
# 以 xin 普通用户执行；rosdep 更新时需要电脑现有代理可用。
bash ~/pi_setup/verify_setup.sh
```

`rosdep update` 本次通过临时命令环境访问电脑代理，没有写入全系统代理。今后更新依赖缓存时可以使用：

```bash
# 只对这一条命令使用代理；若电脑地址改变，请改成实际地址。
https_proxy=http://192.168.0.101:7897 http_proxy=http://192.168.0.101:7897 \
  rosdep update --rosdistro humble
```

完成环境验收时，现有资料分支工作区干净，尚未产生新的 Git 提交；随后按用户要求将本记录与注释脚本提交到 `docs/livox-setup`。GitHub 的登录权限已在 VS Code 远程终端验证，普通 SSH 终端是否能推送还取决于该终端可用的认证方式。
