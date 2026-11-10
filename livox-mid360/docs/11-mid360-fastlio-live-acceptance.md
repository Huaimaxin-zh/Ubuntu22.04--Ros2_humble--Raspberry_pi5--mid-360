# 新卡 MID360 与 FAST-LIO 真机验收记录

日期：2026-11-10，北京时间。本轮在重新烧录的新 SD 卡上完成真实 MID360 输入、FAST-LIO 输出、PCD 保存及正常停止检查。最终完整测试时间为 **12:29:14～12:31:13，结果通过**。没有使用 Livox Viewer 或 RViz。

本记录接续 [软件准备阶段](10-livox-fastlio-new-card-setup.md)。当时的 13 项软件检查确实未启动驱动；本轮接好雷达后才完成以下实机验证，不能把两个阶段混写。原始数据、PCD 和长日志留在树莓派，仓库只保留 [精选结果 JSON](../evidence/2026-11-10-mid360-fastlio-live-acceptance.json)、带注释工具及补丁。

## 最终实收结果

每阶段先预热 5 秒，再实际统计 30 秒。表中速度是观察器收到的消息数除以实际统计秒数，不是配置中的预期值。

| 阶段 | 输入点云 | 输入 IMU | 注册点云 | 里程计 |
| --- | --- | --- | --- | --- |
| 仅驱动输入 | 300 帧 / 10 Hz | 6000 条 / 200 Hz | 本阶段不检查 | 本阶段不检查 |
| 默认 FAST-LIO | 300 帧 / 10 Hz | 6000 条 / 200 Hz | 300 帧 / 10 Hz | 300 条 / 10 Hz |
| 短时保存模式 | 300 帧 / 10 Hz | 6000 条 / 200 Hz | 300 帧 / 10 Hz | 300 条 / 10 Hz |

三阶段的话题类型、单一发布者、正数且递增的时间戳、基础内容检查均通过，没有重复或倒退时间戳，也没有已检查范围内的非法 payload。CustomMsg 每帧约 1.99～2.02 万点，线号均为 0～3；全部收到的 CustomMsg XYZ 都进行了有限性检查。默认算法输出每帧 528～624 点，保存模式每帧 351～630 点；输出较少来自过滤和处理，不能要求它与原始点数相等。

注册点云每帧最多均匀检查 512 个 XYZ；默认阶段共检查 153600 个，保存阶段共检查 135444 个，均为有限非零坐标。里程计位置、四元数数值及四元数归一性通过。各阶段 lidar→imu 最近时间戳差最大约 0.0791 秒；算法阶段 cloud→lidar 最大约 0.1004 秒，odom→cloud 为 0，均在检查器 0.25 秒阈值内。该时间对应检查不等于完成时间标定。

| PCD 保存检查 | 本次实测 |
| --- | --- |
| 保存调用 | 短时保存模式下调用 `/map_save`，随后独立检查文件内容 |
| 路径 | `/home/xin/livox_runtime/maps/mid360_map.pcd` |
| 点数 | 17802，等于 `WIDTH × HEIGHT` |
| 编码 / 每点大小 | binary / 32 字节 |
| 数据区大小 | 569664 字节，精确等于 `17802 × 32` |
| 文件总大小 | 569913 字节 |
| XYZ 检查 | 按头部字段偏移解析，均匀抽查 1024 点，全部有限 |
| SHA256 | `a64df0bbe1c89f4f6ea1751b29c097a956088b904d0f925914bdadb1664c5f31` |

默认 FAST-LIO、保存模式 FAST-LIO、驱动均用单次 SIGINT 正常停止：Launch 返回 0，子节点日志明确显示 `process has finished cleanly`，没有 `process has died`，未升级到 SIGTERM/SIGKILL。结束后无驱动、算法、原生验收器或 gdb 残留进程，`dpkg --audit` 为空，根分区约 21 GB 可用。

## 本轮发现并解决的问题

### Python 观察器的负载影响了 IMU 计数

首轮 Python 观察器使用 `--input-only`，同时处理 CustomMsg 与 IMU 时接近占满一个 CPU 核心，IMU 接收计数偏低；当时尚未启动 FAST-LIO。单独订阅 IMU 能收到约 200 Hz；换为 C++ 直接读取消息后，三个完整阶段都收到 6000 条 / 30 秒，说明不能把早期观察器处理不过来解释为驱动 IMU 发布不足。

最终采用 [`native-verifier`](../scripts/stack/native-verifier/README.md)，主 runner 不自动回退到 Python 点云观察器。软件阶段留档的 `verify_live_stream.py` 保留作历史，不再作为本卡最终同时处理多路数据的验收入口。工具说明包含构建方法、每个函数的阅读顺序、阈值和三个频率口径。

### Launch 正常返回不等于子节点正常退出

早期 runner 同时向 Launch 和整个子进程组发送 SIGINT，叠加 Launch 转发后可能触发重复停止。现在先只给本轮创建的 Launch 主进程发送一次 SIGINT，让它转发；只有超时才对该进程组升级信号。runner 同时检查 Launch 返回码和子节点退出日志。

这个修正使 FAST-LIO 正常退出，但官方驱动仍曾在 SDK 反初始化日志之后以 -11 退出。早期只看 Launch 返回 0 的总体判断不足，未采用其 `passed=true` 作为最终证据。尝试提前清理 PubHandler 的候选驱动补丁也未解决故障，已经回退，不随正式安装发布。

### SDK 与 ROS2 的两套 spdlog 符号冲突

诊断时保留正式 Launch 的九个参数文件，用临时 gdb Launch 复现 SIGSEGV，关键栈为：

```text
SIGSEGV in /lib/aarch64-linux-gnu/libspdlog.so.1
← std::shared_ptr<spdlog::logger>::~shared_ptr()
  in /home/xin/livox_sdk2/lib/liblivox_lidar_sdk_shared.so
← libc exit
```

SDK 内嵌 spdlog 1.3.1，ROS2 Humble 使用系统 spdlog 1.9.2。两个版本对象布局不同；栈显示 SDK logger 析构进入系统 spdlog。此前采用另一种参数传递方式直接运行 gdb 时没有复现，不能据此认定正式 Launch 没问题。

最终在 SDK 的 `sdk_core/CMakeLists.txt` 中，只给 Linux 共享库目标增加 `-Wl,-Bsymbolic`，使 SDK 内部符号引用绑定到自身实现，避免同名 C++ 符号混用。没有修改 ROS2 系统库。补丁见 [SDK 符号绑定补丁](../patches/sdk-spdlog-symbol-binding.patch) 与 [逐项说明](../patches/README.md)。

修复后 SDK 动态段存在 `SYMBOLIC`；修复前后 1574 个动态导出符号名称一致，`ldd -r` 没有未解析库或符号。先完成正式无 gdb 的单驱动 12 秒采集与正常退出，再完成本文三阶段全链路测试。驱动源码恢复为官方基础提交，仅保留本卡配置改变；真正修改的是 SDK 链接配置。

## 最终版本与重新构建方法

SDK 基础提交仍为 `c0796f04c143143899c87a773d9f6b7136453c0b`，再应用本轮符号绑定补丁；驱动为 `21445540f0d100dc86a7e6df312dd70bbdb4afdf`；FAST-LIO 为 `2fffc570a25d0df172720bac034fbdb6a13d2162`，ikd-Tree 为 `e2e3f4e9d3b95a9e66b1ba83dc98d4a05ed8a3c4`。完整哈希见 [版本 JSON](../upstream-versions.json)。文件哈希用于识别本卡产物，不要求其他工具链重新编译得到相同二进制哈希。

已安装环境不需要重跑下面命令。若以后按本卡锁定版本重新构建，先在树莓派 Bash 终端部署正式补丁和新版脚本，不能只使用软件阶段的初版构建脚本：

```bash
# 仓库内补丁只是一份文件；先复制到构建脚本约定的位置。
mkdir -p ~/livox_stack_setup/patches
cp ~/projects/raspberrypi-mid360/livox-mid360/patches/sdk-spdlog-symbol-binding.patch \
   ~/livox_stack_setup/patches/

# 同步含补丁校验的新构建脚本；不涉及 sudo 或系统库。
cp ~/projects/raspberrypi-mid360/livox-mid360/scripts/stack/build_sdk2.sh \
   ~/livox_stack_setup/

# 核对上游提交和补丁，幂等应用后单线程构建用户目录 SDK。
bash ~/livox_stack_setup/build_sdk2.sh
```

[`build_sdk2.sh`](../scripts/stack/build_sdk2.sh) 先锁定 SDK 基础提交，要求补丁存在且 SHA256 正确。反向检查通过表示已应用；否则必须正向检查通过才应用；遇到冲突直接停止，不强行覆盖自定义源码。随后执行原有单线程构建和用户目录安装。修改后的 CMake 本卡为 LF；Windows 上游副本若保留 CRLF，源码文件哈希可能不同，但补丁上下文和逻辑可一致。

这份新版脚本已同步树莓派，通过 `bash -n`，其 SHA256 为 `a4957affe20e35b79e20d178e15501520ed01bebbaa5fe12f4a430ee4270604e`；树莓派正式补丁哈希及反向检查通过。最终 FAST-LIO 继续使用软件阶段成功的 `-O1` 与 GCC 回收参数，单线程构建，没有更改 swap。

## 以后启动与复查

日常运行仍使用两个终端，不启动 Viewer：

```bash
# 终端一：检查 eth0 地址和物理链路后启动驱动。
bash ~/livox_runtime/run_livox.sh
```

```bash
# 终端二：默认配置启动 FAST-LIO，关闭 RViz，不累积整图 PCD。
bash ~/livox_runtime/run_fastlio.sh
```

需要保存时，先 Ctrl+C 停止默认算法，再运行 `bash ~/livox_runtime/run_fastlio.sh --save-map`，在另一个加载 `source ~/livox_runtime/env.sh` 的终端调用 `ros2 service call /map_save std_srvs/srv/Trigger '{}'`。短时保存模式会累积整图，完成后先停算法，再停驱动，不把它当成长期无界缓存。

若要重做本次完整验收，先按 [原生工具说明](../scripts/stack/native-verifier/README.md) 准备和编译检查器，并部署 [`run_live_acceptance.py`](../scripts/stack/run_live_acceptance.py) 与 [`check_saved_pcd.py`](../scripts/stack/check_saved_pcd.py)。确认没有自己已运行的驱动/算法后执行：

```bash
# 把本次编排与PCD检查脚本部署到约定目录；这两条只复制文件。
cp ~/projects/raspberrypi-mid360/livox-mid360/scripts/stack/run_live_acceptance.py \
   ~/projects/raspberrypi-mid360/livox-mid360/scripts/stack/check_saved_pcd.py \
   ~/livox_stack_setup/

# 本脚本会启动真实雷达和算法、短时保存地图，并停止自己创建的节点。
# 它会拒绝已有实例，旧同名地图会先改名保留，日志另存带时间戳的目录。
python3 ~/livox_stack_setup/run_live_acceptance.py
```

runner 检查 eth0 链路和雷达 ping，依次运行三个阶段、调用保存、只读验证 PCD，最终要求三组节点均正常退出才写 `passed=true`。PCD 检查器核对头部字段数组、正数点数、宽高、精确 payload 长度、按字段偏移抽样 XYZ 以及 SHA256，不把二进制地图直接当文本打印。

本卡网络保持 eth0 `192.168.123.4/24` → 雷达 `192.168.123.20`，Wi-Fi 用于 SSH 和上网，Domain 10。驱动实际读工作空间源码对应的 `MID360_config.json`，runtime 内 JSON 为记录副本；FAST-LIO 实际读 runtime 中的两份 YAML。仓库文件不会在 push 后自动部署，具体路径见 [新卡配置说明](../configs/pi5/README.md)。

## 验收结论的范围

本次证明新卡上真实采集、短时 FAST-LIO 输出、基础几何数值、PCD 结构与抽样内容，以及正常退出已跑通。没有重新标定外参，没有测量绝对建图精度、闭环、跨 Wi-Fi 点云传输或长期稳定性。该结果不改变旧 SD 卡维修失败的历史结论。
