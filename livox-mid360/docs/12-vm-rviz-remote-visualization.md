# 在 Ubuntu 虚拟机远程显示树莓派 FAST-LIO

日期：2026-11-10。本次已准备并部署远程 RViz 配置，树莓派和 Ubuntu 虚拟机之间的基础 ping 已通过。**尚未在虚拟机实测 DDS 消息接收和 RViz 渲染，因此当前不能写成“远程可视化已经跑通”。** 树莓派本机的真实采集、FAST-LIO 输出和正常停止结果见 [前一轮实机验收](11-mid360-fastlio-live-acceptance.md)。

树莓派继续运行驱动和 FAST-LIO；虚拟机订阅算法输出并负责显示。本方案使用 ROS2 的 RViz，不需要 Livox Viewer，也不需要在虚拟机再编译 Livox 驱动或 FAST-LIO。

## 地址、文件与运行位置

| 项目 | 本次值 |
| --- | --- |
| Ubuntu 虚拟机 | `192.168.0.102`，执行本文中的显示命令 |
| 树莓派 Wi-Fi | `192.168.0.103`，SSH 用户 `xin` |
| 树莓派雷达专用 eth0 | `192.168.123.4/24`，继续接收 MID360，不为显示修改它 |
| MID360 | `192.168.123.20` |
| ROS_DOMAIN_ID | `10` |
| RMW | `rmw_fastrtps_cpp` |
| 树莓派已部署配置 | `/home/xin/livox_runtime/rviz/remote_pi5.rviz` |
| 仓库归档 | [remote_pi5.rviz](../configs/rviz/remote_pi5.rviz)、[配置说明](../configs/rviz/README.md) |

Wi-Fi 地址可能随 DHCP 改变。本文的代码块是 **Ubuntu 虚拟机 Bash 命令**，不是 Windows PowerShell，也不是树莓派终端命令。显示配置的复制不会启动、停止或重新配置树莓派上的雷达节点。

## 在虚拟机准备配置和 ROS2 环境

先确认虚拟机可以运行 ROS2 Humble 和 RViz。若本机缺少 `rviz2`，需在虚拟机安装对应的 `ros-humble-rviz2` 软件包；不需要在无桌面的树莓派安装它。

```bash
# 查看虚拟机当前IPv4地址；本次显示端为192.168.0.102。
ip -br -4 addr

# 复查到树莓派Wi-Fi的基础可达性；成功只代表ICMP可达。
ping -c 3 192.168.0.103

# 在虚拟机创建显示配置目录，不涉及SD卡分区或树莓派文件。
mkdir -p ~/livox_remote

# 用SSH复制树莓派上已部署的RViz配置；密码只在终端内输入。
scp xin@192.168.0.103:/home/xin/livox_runtime/rviz/remote_pi5.rviz \
    ~/livox_remote/remote_pi5.rviz

# 加载虚拟机自己的ROS2 Humble，不加载树莓派ARM64安装目录。
source /opt/ros/humble/setup.bash

# 与树莓派当前运行节点使用相同的DDS域。
export ROS_DOMAIN_ID=10

# 允许跨主机ROS2通信，不能限制为本机回环。
export ROS_LOCALHOST_ONLY=0

# 使用与本次树莓派相同的Fast DDS实现。
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp

# 只查询RViz包位置；找不到时先解决虚拟机RViz安装。
ros2 pkg prefix rviz2
```

如果 `scp` 报远程配置不存在，应先把仓库配置部署到树莓派上述路径；这不是重新安装雷达软件的理由。SSH 使用虚拟机自己的密钥和 known_hosts，不依赖 Windows 的 `raspberrypi-livox` 别名。

每个新开的虚拟机终端都要加载上述 ROS2 环境并设置三个变量。若树莓派曾通过 `LIVOX_ROS_DOMAIN_ID` 改过域号，应使用节点实际启动时的值，不能只改显示端。

## 先检查实际接收，再打开 RViz

```bash
# 查看注册点云的类型和远端发布者；应为标准PointCloud2。
ros2 topic info /cloud_registered --verbose

# 查看里程计的类型和发布者；应为nav_msgs/msg/Odometry。
ros2 topic info /Odometry --verbose

# 测量虚拟机实际收到的点云；观察数秒后按Ctrl+C结束本检查。
# Humble此命令不添加不受支持的--qos-reliability选项。
ros2 topic hz /cloud_registered --window 100

# 加载专用显示配置；不要在虚拟机另启驱动或第二份FAST-LIO。
rviz2 -d ~/livox_remote/remote_pi5.rviz
```

树莓派本机前一轮测得 `/cloud_registered` 约 10 Hz；这不能替代虚拟机自己的接收测量。`topic info` 看见发布者，也不能替代 `topic hz` 持续收到消息和 RViz 实际渲染。

| RViz 项目 | 当前设置与作用 |
| --- | --- |
| Fixed Frame | `camera_init`，与 FAST-LIO 的注册点云坐标系一致 |
| CloudRegistered | `/cloud_registered`，标准 PointCloud2，按 Z 高度着色 |
| 点云 QoS | Best Effort / Volatile / Depth 5 |
| 点云外观 | Points，3 像素，初始观察距离 15 米 |
| Decay Time | 30 秒，只在虚拟机显示最近窗口内的点云 |
| TF | 显示 `camera_init → body` |
| Odometry | `/Odometry`，箭头显示，Reliable / Volatile |
| Path、CloudMap、CloudEffected | 关闭，与树莓派默认 `path_en/map_en/effect_map_en=false` 对应 |

FAST-LIO 点云发布者的 Reliable 可以匹配 RViz 的 Best Effort 订阅；显示端允许跳过 Wi-Fi 丢失帧。原始 `/livox/lidar` 是 Livox CustomMsg，不能直接填入标准 PointCloud2 显示项。此方案订阅标准算法输出，因此显示端不需要 Livox 自定义消息接口。

30 秒点云窗口不是永久完整地图，较早的点会消失。无需为此打开树莓派的整图或 PCD 累积；如需更多最近历史，可在虚拟机适度调大 Decay Time，同时观察虚拟机内存和渲染负载。

## 收不到或看不到时怎样区分

1. `ping` 不通：先检查双方当前 Wi-Fi / 桥接局域网地址和 VMware 网卡连接，不修改雷达专用 eth0。
2. `ping` 通但没有远端发布者：核对双方 Domain、RMW 和 `ROS_LOCALHOST_ONLY=0`，再排查防火墙、AP 客户端隔离及 DDS 组播发现。
3. 有发布者但 `topic hz` 没有实际数据：继续排查双向 UDP 传输和实际 QoS。发现成功不代表数据通道已经可达。
4. `topic hz` 有数据但 RViz 没点：看 CloudRegistered 的 Status，确认 Fixed Frame 为 `camera_init`、话题正确、显示项启用，并调整视角。

如果虚拟机曾在另一 Domain 下启动 ROS2 CLI daemon，可在已设置正确环境的虚拟机终端刷新它；这只影响该虚拟机的查询守护进程：

```bash
# 停止虚拟机旧环境下的ROS2 CLI daemon，不停止树莓派雷达节点。
ros2 daemon stop

# 按当前终端的域和RMW重新启动查询daemon。
ros2 daemon start
```

本次双方已有同一局域网地址，优先沿用现有连接。如果以后把虚拟机改到 NAT 私网，只设置 initial peers 或 Discovery Server 不保证数据能回传，仍需双方实际可达；桥接局域网更便于直接排查。

## 后续验收应补记什么

完成现场操作后，应补记虚拟机的实际点云接收速度、RViz CloudRegistered 状态、TF 是否可用和真实显示结果。当前只确认基础 ping 和配置准备，DDS 订阅、渲染性能及跨 Wi-Fi 长期稳定性仍待测试。

配置派生自 FAST-LIO 上游 `fastlio.rviz`，原项目版权和许可继续适用，来源见 [配置说明](../configs/rviz/README.md)。资源观察工具及其 CPU/GPU 口径见 [下一篇](13-pi5-resource-monitor.md)。
