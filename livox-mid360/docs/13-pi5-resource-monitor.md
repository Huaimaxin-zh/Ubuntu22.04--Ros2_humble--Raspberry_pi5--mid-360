# 树莓派5 CPU、GPU、内存与温度监控

日期：2026-11-10。本次新增只读脚本 [monitor_resources.py](../runtime/pi5/monitor_resources.py)，已部署为树莓派 `~/livox_runtime/monitor_resources.py`。脚本只使用 Python 标准库，无需 sudo、pip 或额外监控软件包；按 Ctrl+C 只结束监控，雷达和 FAST-LIO 继续运行。

监控在树莓派终端运行，显示的是树莓派资源；在 Ubuntu 虚拟机运行 RViz 时，虚拟机的渲染开销属于虚拟机及其宿主机，不会变成树莓派 GPU 的负载。

## 运行与保存输出

以下均为树莓派 `xin` 的 Bash 命令。脚本不依赖 ROS2 环境，无需先 source 工作空间。

```bash
# 查看参数说明，不启动雷达或算法。
python3 ~/livox_runtime/monitor_resources.py --help

# 默认每秒刷新，持续运行；按Ctrl+C结束监控。
python3 ~/livox_runtime/monitor_resources.py

# 每2秒显示一次，共显示5次；保留历史输出而不清屏。
python3 ~/livox_runtime/monitor_resources.py --interval 2 --samples 5 --no-clear

# 创建日志目录；只写入树莓派用户目录。
mkdir -p ~/livox_runtime/logs

# 每秒记录一次，共60次；tee同时显示并保留本次文本输出。
python3 ~/livox_runtime/monitor_resources.py --interval 1 --samples 60 --no-clear \
  | tee ~/livox_runtime/logs/resources-$(date +%Y%m%d-%H%M%S).log
```

`--interval` 范围为 0.2～60 秒，默认 1 秒。`--samples 0` 表示持续运行，正数表示有限次数，负数会被拒绝。默认只有交互终端会清屏，`--no-clear` 明确保留每次输出。第一条结果需要等待一个采样间隔，因为占用率由两次累计计数的差计算。

脚本输出明确使用北京时间；上述日志文件名中的 `date` 则采用树莓派系统时区。系统若仍为 UTC，文件名时间与正文显示相差 8 小时，这是命名口径差异。

仓库归档与运行目录分别管理。若以后需要同步修改，应先比较自己的实际文件，再复制；复制本身不会运行监控：

```bash
# 将已经审阅的仓库脚本复制到约定运行路径；不会自动启动它。
cp ~/projects/raspberrypi-mid360/livox-mid360/runtime/pi5/monitor_resources.py \
   ~/livox_runtime/monitor_resources.py
```

## CPU 总体与进程 CPU 为什么不一样

脚本从 `/proc/stat` 读取总体和每核累计时间，只使用前 8 列，避免把 guest 时间重复计入。`idle + iowait` 按未执行计算处理，两个采样之间计算：

```text
CPU总体占用 = 100 ×（总时间增量 − idle和iowait增量）÷ 总时间增量
```

这一总体指标把所有核心合在一起归一化，全机满载为 100%；每核行则显示该核心满载为 100%。进程行从 `/proc/PID/stat` 的用户态与内核态 CPU tick 增量计算，**一个核心满载为 100%**，多线程进程跨核时可以超过 100%。

因此，在四核树莓派上，单个进程占用 20% 单核约对应全机 5% 的计算能力，不能把进程的 20% 与 CPU 总体的 6% 直接比较或认为显示矛盾。不同文件的读取时刻也存在微小差异，不应强求逐项相加精确相等。

进程以 PID 加启动时间识别，避免 PID 复用导致错误差分；显示 CPU 使用最多的前 5 个进程。采样期间刚启动、结束或暂时不可读的进程会跳过，这是短时间差分观察，不是系统的完整进程审计。

## GPU 四个引擎的计算口径

脚本自动寻找 `/sys/class/drm/card*/device/gpu_stats`，不假定固定 card 编号。该接口提供每个队列的采样时间、累计任务数和累计忙碌时间，时间单位为纳秒。每个引擎分别计算：

```text
单个引擎占用 = 100 × 累计忙碌纳秒增量 ÷ 采样时间纳秒增量
```

| 输出项 | 含义 |
| --- | --- |
| `bin` | V3D 的 binning 引擎 |
| `render` | 渲染引擎 |
| `tfu` | 纹理格式处理引擎 |
| `csd` | 计算调度引擎 |

这些引擎可能同时工作，**不能把四个百分数相加当作 GPU 总体占用**。它们来自实际忙碌时间差分，也不是 GPU 频率、显存使用量或由频率推算的“占用率”。内核接口中名为 `cpu`、`cache_clean` 的项目属于 V3D 辅助队列，不是 `/proc/stat` 的 CPU 总体，也不加入这里的四个 GPU 引擎百分数。

接口缺失、无读取权限、计数重置或时间差非法时显示 `N/A`；这不同于成功读取后测得的 0.0%。某个短窗口四个引擎都是 0，只说明该窗口这些引擎没有累计到忙碌时间，不能证明 GPU 永远没有负载或已经通过性能测试。

本次树莓派负责驱动和 FAST-LIO，不在本机打开 RViz，四引擎为 0 符合这一运行方式。远程 RViz 的显示工作应在虚拟机另行观察，不能由树莓派 GPU 数据代替。

## 内存与温度的含义

系统内存采用 `MemTotal − MemAvailable`，而不是简单的 `MemTotal − MemFree`，避免把可回收缓存全部当成不可用内存。输出单位为 MiB。进程内存从 RSS 页数乘系统页大小换算，只表示驻留内存；共享页可能同时计入多个进程，不应直接求和当作系统内存使用。

CPU 温度读取 `/sys/class/thermal/thermal_zone0/temp`，把毫摄氏度除以 1000 显示；接口不可读时为 `N/A`。脚本不改变风扇、频率、供电或温控策略，也不测量功耗。

## 本次三次短时观察

以下为本次已取得的三个短时样本。进程 CPU 均使用“单核满载为 100%”口径，CPU 总体使用“全机满载为 100%”口径。

数值转录自此前实机命令输出，没有保留独立的原始终端日志；本次归档没有重新采样。原输出时间为树莓派 UTC `05:06:33～05:06:35`，对应北京时间 `13:06:33～13:06:35`。随后仅将脚本显示时间改为北京时间并重新部署，通过 Python 编译检查；上述样本采自时间显示调整之前，计算公式未改变。来源、文件哈希与验证范围见 [精选记录 JSON](../evidence/2026-11-10-remote-rviz-resource-monitor.json)。

| 指标 | 第1次 | 第2次 | 第3次 |
| --- | --- | --- | --- |
| CPU 总体 | 5.9% | 6.1% | 6.4% |
| FAST-LIO 进程 CPU | 19.7% | 20.7% | 19.8% |
| 驱动进程 CPU | 10.9% | 10.8% | 11.9% |
| GPU bin / render / tfu / csd | 均为 0.0% | 均为 0.0% | 均为 0.0% |
| 系统内存 | 1139 / 3984 MiB | 1141 / 3984 MiB | 1139 / 3984 MiB |
| CPU 温度 | 57.9 °C | 57.3 °C | 57.9 °C |

这些是当时运行条件下的短时采样，不是长期稳定性结论或 benchmark，也不代表运动建图、不同场景、不同输出密度下负载相同。完整应用通过性仍以 [实机验收记录](11-mid360-fastlio-live-acceptance.md) 为依据；虚拟机远程接收和渲染状态见 [远程可视化记录](12-vm-rviz-remote-visualization.md)。

## 按函数理解脚本

| 函数 | 作用 |
| --- | --- |
| `read_cpu`、`cpu_percent` | 读取累计 CPU 时间，再用前后差分计算总体及每核百分数 |
| `read_gpu`、`gpu_percent` | 寻找可读 GPU 统计接口，按各引擎纳秒计数分别计算；异常时返回 N/A |
| `read_processes` | 读取进程名、CPU tick、RSS 和启动时间，处理进程在读取中消失的情况 |
| `memory_and_temperature` | 用 MemAvailable 口径显示内存，并读取 CPU 温度 |
| `positive_interval` | 限制采样间隔，拒绝超范围输入 |
| `main` | 保存前次计数、等待间隔、再次采样、显示差分；达到次数或 Ctrl+C 后结束 |

Python 源码的中文注释解释字段与公式。脚本只读 `/proc`、`/sys` 并向终端输出；使用带 `tee` 的命令时，日志文件由命令行显式创建，不会自动上传到 GitHub。

V3D 统计字段的单位和队列来自本次内核对应的树莓派 Linux 分支：[v3d_sysfs.c](https://github.com/raspberrypi/linux/blob/rpi-6.8.y/drivers/gpu/drm/v3d/v3d_sysfs.c)、[v3d_sched.c](https://github.com/raspberrypi/linux/blob/rpi-6.8.y/drivers/gpu/drm/v3d/v3d_sched.c)。其他系统或内核未必提供相同接口；本次运行环境为 Ubuntu 22.04.5 ARM64、`6.8.0-1047-raspi`。
