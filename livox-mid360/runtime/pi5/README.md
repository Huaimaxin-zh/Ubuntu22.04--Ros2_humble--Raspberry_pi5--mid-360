# 新卡运行脚本：使用本目录

**2026-11-10 重新烧录的新卡使用本目录的环境、两个启动脚本和资源监控脚本。** 上一级 `runtime/env.sh`、`runtime/run_livox.sh` 和旧检查器属于旧卡独立恢复环境的历史留档，不要用它们覆盖当前树莓派环境。

这些文件已经部署到树莓派 `~/livox_runtime`。它们使用系统 ROS2 Humble、`~/ws_livox/install`、`~/ws_fastlio/install` 和 `~/livox_sdk2/lib`，不是旧卡私有 ROS 依赖布局。

| 文件 | 用途 |
| --- | --- |
| `env.sh` | 加载 ROS2 → 驱动 → FAST-LIO，设置 SDK 共享库路径与默认 Domain 10 |
| `run_livox.sh` | 检查 eth0 地址和物理链路，启动官方 CustomMsg 驱动 Launch，无 Viewer |
| `run_fastlio.sh` | 读取 runtime 中的 FAST-LIO YAML，关闭 RViz；可选短时 `--save-map` |
| `monitor_resources.py` | 普通用户只读监控 CPU、V3D GPU 各引擎、进程、内存和 CPU 温度；Python 标准库，无需加载 ROS |

当前真实采集与 FAST-LIO 三阶段验收已完成：点云 10 Hz、IMU 200 Hz、算法注册点云和里程计 10 Hz，PCD 保存及正常停止通过。具体两终端方法、SDK 退出修复和原生验收工具见 [实机记录](../../docs/11-mid360-fastlio-live-acceptance.md)。

## 仓库文件和实际运行目录

修改 Git 仓库文件、保存或推送，都不会自动替换运行目录中的脚本。若以后修改本目录，应先检查差异和已有运行文件，再人工部署；以下命令只复制脚本，不启动节点：

```bash
# 树莓派 xin 终端：创建并确认实际运行目录。
mkdir -p ~/livox_runtime

# 把版本记录中的环境、启动和监控脚本复制到实际运行目录。
cp ~/projects/raspberrypi-mid360/livox-mid360/runtime/pi5/env.sh \
   ~/projects/raspberrypi-mid360/livox-mid360/runtime/pi5/run_livox.sh \
   ~/projects/raspberrypi-mid360/livox-mid360/runtime/pi5/run_fastlio.sh \
   ~/projects/raspberrypi-mid360/livox-mid360/runtime/pi5/monitor_resources.py \
   ~/livox_runtime/
```

已经存在自定义运行脚本时，先备份并比较再复制。配置文件单独部署，见 [configs/pi5](../../configs/pi5/README.md)。这里只加载环境不会启动设备：

```bash
# 加载本卡已经编译成功的环境。
source ~/livox_runtime/env.sh
```

默认关闭整图、轨迹与 PCD 累积；`--save-map` 用于短时保存检查，完整地图缓存会增长。本次保存阶段为预热 5 秒和统计 30 秒，另有服务调用与停止时间；不把建议时长当成实际测量时长。FAST-LIO 上游部分日志仍写源码 `Log/`，不意味着关闭了所有文件写入。

## 只读查看资源占用

另开树莓派终端运行，不会启动或停止雷达与算法：

```bash
# 默认每秒刷新，Ctrl+C 只结束监控。
python3 ~/livox_runtime/monitor_resources.py

# 输出三次并保留结果，适合人工对照。
python3 ~/livox_runtime/monitor_resources.py --samples 3 --no-clear
```

指标口径、GPU 为零或 N/A 的含义及本次短时测量见 [资源监控说明](../../docs/13-pi5-resource-monitor.md)。虚拟机显示配置单独放在 [configs/rviz](../../configs/rviz/README.md)。
