# 本次 MID360 配置全过程

这是一份本次实际工作的流程记录。适用环境为 Ubuntu 22.04 ARM64、ROS2 Humble、树莓派 5 和 MID360。原系统已有文件损坏，恢复环节采用了私有依赖和独立工具链，因此不能把本记录当作任意新机器的通用一键安装命令。

## 阶段 1：确认系统和需求

需要完成的链路：MID360 通过网线向树莓派提供数据，树莓派运行 `livox_ros_driver2`，发布点云和 IMU。此次不把原始数据持续保存到 U 盘，也不在树莓派启动 RViz。

检查命令：

```bash
# 系统发行版：本次为 Ubuntu 22.04.5 LTS。
cat /etc/os-release
# CPU 架构：本次为 aarch64。
uname -m
# 已加载的 ROS 发行版：本次为 humble。
echo "$ROS_DISTRO"
# 内存、可用存储和 inode，用于区分资源不足与文件损坏。
free -h
df -h / /var
df -i / /var
```

这些输出写入记录时，不要只写“Ubuntu”。ROS 版本、系统版本和架构会影响依赖包选择。

## 阶段 2：确认雷达地址和网络职责

前期抓包中，雷达从 `192.168.123.20` 向接收端 `192.168.123.4` 发 UDP 数据，进一步 ping 和邻居表也确认了 `.20` 是雷达地址。

最终接线和地址：

```text
MID360 192.168.123.20
    │ 供电正常，数据网线连接
    ▼
树莓派 eth0 192.168.123.4/24

Windows ── Wi-Fi / SSH ── 树莓派 wlan0（本次为192.168.0.103）
```

树莓派恢复临时网口配置：

```bash
# 只启用雷达专用网口，不动 Wi-Fi。
sudo ip link set eth0 up
# 配置接收 IP；不添加网关，避免影响管理网络。
sudo ip address replace 192.168.123.4/24 dev eth0

# 发送到雷达的路由应显示 dev eth0、src 192.168.123.4。
ip route get 192.168.123.20
# carrier=1 才表示物理链路已经建立。
cat /sys/class/net/eth0/carrier
# ping 成功只能确认网络连接，还不能代替点云验收。
ping -c 3 192.168.123.20
```

本次发生过两种独立情况：临时 IP 在重启后丢失，以及接线未完成时 `NO-CARRIER`。恢复地址并接好供电和网线后，ping 3/3 成功。

## 阶段 3：准备驱动源码和 MID360 JSON

原工作区为 `/home/xin/ws_livox/src/livox_ros_driver2`。JSON 示例保存在 [configs/MID360_config.example.json](../configs/MID360_config.example.json)。

最关键的是区分：

| JSON 字段 | 此次值 | 意义 |
| --- | --- | --- |
| `lidar_configs[0].ip` | `192.168.123.20` | 雷达本身 |
| `MID360.host_net_info.cmd_data_ip` | `192.168.123.4` | 接收命令数据的主机地址 |
| `push_msg_ip`、`point_data_ip`、`imu_data_ip` | `192.168.123.4` | 主机对应通道接收地址 |
| `pcl_data_type` | `1` | 本次使用的数据配置 |
| `pattern_mode` | `0` | 本次扫描配置 |

这里的接收端必须是雷达能到达的树莓派有线地址。不能将 `.20` 同时设置给树莓派网口。

修改 JSON 时先备份原文件，保存修改后重启驱动。备份文件不会自动覆盖运行配置；只修改 JSON 不需要重新编译。

## 阶段 4：识别构建阻碍

原流程先遇到缺少 PCL 开发包，随后 APT/dpkg 无法解析文件，ROS Python/CMake、部分动态库、SDK 和编译环境也出现了损坏证据。磁盘空间当时仍充足，不能把这些错误简单归因于空间不够。

没有为跑通驱动而继续覆盖系统 ROS 或重建包管理数据库。先将原工作区源码和 JSON 备份到 Windows，再在独立副本里处理。

本次采用的准备方式：

1. 沿用已经核查的 ROS2 路径去除未使用 PCL 依赖的调整。
2. 在工作副本继续移除未使用 APR 依赖。
3. 官方 ROS/Ubuntu ARM64 包按 SHA256 校验后解压到用户目录。
4. 获取干净 GCC/sysroot，避开原损坏编译器和标准头文件。
5. 从官方重新取得干净 SDK2 源码，单线程构建共享库。

完整错误证据、判断依据和修复边界见 [故障报告](04-troubleshooting-report.md)。

## 阶段 5：编译 SDK 和驱动

本次 SDK 版本查询返回 1.5.2，源码 commit 和驱动 commit 记录在 [upstream-versions.json](../upstream-versions.json)。

编译采用以下策略：

- 大部分源码副本和中间文件放 `/dev/shm`，减少 SD 编译写入。
- `MAKEFLAGS=-j1`、`CMAKE_BUILD_PARALLEL_LEVEL=1` 限制并行度。
- 驱动使用 `ROS_EDITION=ROS2`、`DISTRO_ROS=humble`、Release。
- 禁用本次不需要的测试、符号链接安装和 Rust 消息生成。
- 最终文件安装到 `/home/xin/livox_runtime`，运行不依赖 RAM 构建缓存。

当时的具体命令在 [archive/session-scripts](../archive/session-scripts/) 中留档。它们依赖已准备的工具链和目录，不能在重启后的空 RAM 目录直接执行。已装好的驱动不需要反复编译。

## 阶段 6：启动前和停止行为检查

为避免误用原损坏环境，编写了 `env.sh` 和 `run_livox.sh`。启动脚本自动加载独立环境，检查有线地址与 carrier，再执行官方编译出的驱动节点。

无数据测试还发现了退出等待线程没有被唤醒的问题。修改工作副本的退出流程后，SIGINT 可以正常结束并释放 SDK。原工作区文件保留，修改差异见 [patches](../patches/README.md)。

动态库检查确认没有缺失依赖，最终安装程序也没有依赖 `/dev/shm` 路径。

## 阶段 7：真实数据验收

先启动驱动：

```bash
bash ~/livox_runtime/run_livox.sh
```

另开终端：

```bash
source ~/livox_runtime/env.sh
python3 ~/livox_runtime/verify_livox_stream.py
```

第一次普通 Python 订阅器被大型 CustomMsg 解析拖慢。改为原生 C++ 检查器后，不降低通过门槛；预热 5 秒再统计 25 秒，测得点云 10.0002 Hz、IMU 199.994 Hz，内容检查通过。

原始结果：[evidence/2026-11-09-stream-result.json](../evidence/2026-11-09-stream-result.json)。检查范围包括所有接收帧的点数、所有接收点的有限坐标、递增时戳和 IMU 六轴有限值。它没有验证外参标定或 FAST-LIO 建图。

## 阶段 8：保存和长期管理

完整运行恢复包保存在 Windows，源码和说明适合放 Git。本仓库保存较小的代码、配置示例、补丁和 JSON 结果；不提交第三方安装库、密钥和原始点云。

后续通过 [Remote-SSH](01-remote-ssh.md) 在 VS Code 操作树莓派，按 [Git 教程](02-git-and-github.md) 提交脚本和问题记录。每解决一个问题，更新对应 Markdown 和代码，一起提交，才能把过程持续补全。
