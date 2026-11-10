# 新卡运行脚本：使用本目录

**2026-11-10 重新烧录的新卡使用本目录这三个脚本。** 上一级 `runtime/env.sh`、`runtime/run_livox.sh` 和旧检查器属于旧卡独立恢复环境的历史留档，不要用它们覆盖当前树莓派环境。

这些文件已经部署到树莓派 `~/livox_runtime`。它们使用系统 ROS2 Humble、`~/ws_livox/install`、`~/ws_fastlio/install` 和 `~/livox_sdk2/lib`，不是旧卡私有 ROS 依赖布局。

| 文件 | 用途 |
| --- | --- |
| `env.sh` | 加载 ROS2 → 驱动 → FAST-LIO，设置 SDK 共享库路径与默认 Domain 10 |
| `run_livox.sh` | 检查 eth0 地址和物理链路，启动官方 CustomMsg 驱动 Launch，无 Viewer |
| `run_fastlio.sh` | 读取 runtime 中的 FAST-LIO YAML，关闭 RViz；可选短时 `--save-map` |

当前软件检查已经完成，**本轮未启动雷达驱动，用户通知接好雷达后再执行运行步骤**。具体两终端方法、预计频率和实际验收工具见 [完整记录](../../docs/10-livox-fastlio-new-card-setup.md#待用户通知后两终端运行与真机验收)。

## 仓库文件和实际运行目录

修改 Git 仓库文件、保存或推送，都不会自动替换运行目录中的脚本。若以后修改本目录，应先检查差异和已有运行文件，再人工部署；以下命令只复制脚本，不启动节点：

```bash
# 树莓派 xin 终端：创建并确认实际运行目录。
mkdir -p ~/livox_runtime

# 把版本记录中的三个脚本复制到它们约定的实际运行目录。
cp ~/projects/raspberrypi-mid360/livox-mid360/runtime/pi5/env.sh \
   ~/projects/raspberrypi-mid360/livox-mid360/runtime/pi5/run_livox.sh \
   ~/projects/raspberrypi-mid360/livox-mid360/runtime/pi5/run_fastlio.sh \
   ~/livox_runtime/
```

已经存在自定义运行脚本时，先备份并比较再复制。配置文件单独部署，见 [configs/pi5](../../configs/pi5/README.md)。这里只加载环境不会启动设备：

```bash
# 加载本卡已经编译成功的环境。
source ~/livox_runtime/env.sh
```

默认关闭整图、轨迹与 PCD 累积；`--save-map` 用于后续 60–120 秒短时检查，完整地图缓存会增长。FAST-LIO 上游部分日志仍写源码 `Log/`，不意味着关闭了所有文件写入。
