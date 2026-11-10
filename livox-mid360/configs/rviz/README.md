# Ubuntu 虚拟机显示树莓派 FAST-LIO

本目录提供远程 RViz 显示配置，不修改树莓派网络或算法，不启动或停止树莓派节点。当前驱动与 FAST-LIO 保持运行，虚拟机只订阅已有输出。

**状态：配置已准备，尚未在 Ubuntu 虚拟机验证真实订阅和 RViz 渲染。** 以下步骤需在虚拟机执行；本次 VM 地址为 `192.168.0.102`，树莓派 Wi-Fi 地址为 `192.168.0.103`，地址可能随 DHCP 改变。

## 在虚拟机 Bash 终端执行

```bash
# 把树莓派已部署的显示配置复制到虚拟机；不依赖 Windows 的 SSH 别名。
mkdir -p ~/livox_remote
scp xin@192.168.0.103:/home/xin/livox_runtime/rviz/remote_pi5.rviz \
    ~/livox_remote/remote_pi5.rviz

# 使用虚拟机本地 ROS2，与树莓派默认通信环境一致。
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=10
export ROS_LOCALHOST_ONLY=0
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp

# 核实远程标准点云的发布端点。
ros2 topic info /cloud_registered --verbose

# 加载显示配置；不要在虚拟机再启动驱动或另一份 FAST-LIO。
rviz2 -d ~/livox_remote/remote_pi5.rviz
```

若 `scp` 提示配置文件不存在，先完成树莓派该路径的文件部署；无需重装雷达软件。若没有 `rviz2`，虚拟机需要安装 `ros-humble-rviz2`。上述命令不是 Windows PowerShell 命令，也不应在树莓派终端执行。若树莓派启动时曾覆盖 `LIVOX_ROS_DOMAIN_ID`，两端域号须使用同一实际值。

## 显示配置与当前算法的对应关系

| 项目 | 设置与理由 |
| --- | --- |
| 固定坐标系 | `camera_init`，与 FAST-LIO 注册点云及里程计相同，无需额外发布 `map` 变换 |
| 主点云 | `/cloud_registered`，标准 PointCloud2；Best Effort / Volatile / Depth 5 |
| 点云样式 | 按 Z 高度着色、Points、3 像素，初始观察距离 15 米 |
| Decay Time | 30 秒；最近点云在虚拟机累积显示，超过窗口会消失，不是持久完整地图 |
| TF / 位姿 | TF 和 `/Odometry` 箭头开启；变换为 `camera_init → body` |
| 空显示 | Path、CloudMap、CloudEffected 关闭，与当前 `path_en/map_en/effect_map_en=false` 一致 |

树莓派默认 `scan_publish_en=true`、`dense_publish_en=false`、`scan_bodyframe_pub_en=true`，保留过滤后的注册点云和机体点云；本显示只订阅前者。`pcd_save_en=false`，不为远程显示打开树莓派的整图累积。原始 `/livox/lidar` 是 CustomMsg，标准 RViz 无法直接当 PointCloud2 显示；接收上述标准输出无需在虚拟机编译 Livox 驱动或 FAST-LIO。

FAST-LIO 点云发布端使用 Reliable / Volatile，RViz Best Effort 订阅可兼容，并允许跳过 Wi-Fi 丢失的显示帧。里程计保留上游 Reliable / Volatile。需要更多最近历史时，可在虚拟机适度增加 Decay Time，同时关注虚拟机内存与渲染负载。

## 没看到点云时

在另一个**同样加载上述环境**的虚拟机终端测量实际接收，观察数秒后 Ctrl+C：

```bash
# Humble 该命令不使用 --qos-reliability 参数。
ros2 topic hz /cloud_registered --window 100
```

有发布端点不等于已收到数据；同时看 RViz 的 CloudRegistered Status。双方 ping 通只证明 ICMP 可达，DDS 仍需双向 UDP 发现与传输；先核对域号、RMW、localhost 设置，再排查防火墙、AP 客户端隔离和组播。当前已在同一局域网，优先沿用现有连接，不改雷达专用 eth0。

若以后把 VM 改到 NAT 私网，仅配置 initial peers 或 Discovery Server 不保证数据可回传；优先使用双方能直接到达的桥接局域网。无需为准备显示而停止现有树莓派节点。

配置派生自 [Ericsii/FAST_LIO_ROS2 fastlio.rviz](https://github.com/Ericsii/FAST_LIO_ROS2/blob/2fffc570a25d0df172720bac034fbdb6a13d2162/rviz/fastlio.rviz)，原项目版权与 [GPLv2](https://github.com/Ericsii/FAST_LIO_ROS2/blob/2fffc570a25d0df172720bac034fbdb6a13d2162/LICENSE) 继续适用。仅调整既有 ROS2 RViz 字段；显示效果仍待虚拟机现场验收。
