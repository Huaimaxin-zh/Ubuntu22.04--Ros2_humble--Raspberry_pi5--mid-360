# 新卡 Livox-SDK2、livox_ros_driver2 与 FAST-LIO 软件配置记录

日期：2026-11-10，北京时间。设备为树莓派5、Ubuntu 22.04.5 ARM64、ROS2 Humble，用户名 `xin`。本文记录新 SD 卡的软件配置，不改变旧卡维修报告的结论。

**本轮按用户要求完成软件准备，没有启动雷达驱动、真实雷达采集或实机建图。** FAST-LIO 确实在独立 Domain 177、本机通信范围内短暂启动过，用于无输入初始化检查，随后正常退出。后续接线、雷达数据、建图和地图保存验收，需要用户通知后另行进行。软件检查通过不能写成“雷达与建图已经实机跑通”。本轮不安装或使用 Livox Viewer，FAST-LIO 启动参数也设为 `rviz:=false`。

本记录接续 [新卡 ROS2 / Git 配置](09-ros2-git-new-card-setup.md)。源码脚本见 [scripts/stack](../scripts/stack/README.md)，新卡运行脚本见 [runtime/pi5](../runtime/pi5/README.md)，配置记录见 [configs/pi5](../configs/pi5/README.md)，完整软件验收见 [结果 JSON](../evidence/2026-11-10-livox-fastlio-software-ready.json)。

## 最终软件验收结果

| 检查项目 | 实际结果 |
| --- | --- |
| ROS2 Humble 基础环境 | 已在前一阶段完成安装，本机 C++ → Python 通信及 colcon 示例通过 |
| Livox-SDK2 | 编译并安装到用户目录，退出码 0 |
| PCL、Eigen、APR 与 ROS 转换依赖 | 实际安装完成，普通用户复核退出码 0，打印 `DEPENDENCIES_VERIFIED_OK` |
| livox_ros_driver2 | 编译成功，`CustomMsg` 可读取 |
| FAST-LIO | 最终以 `-O1` 和 GCC 内存回收参数单线程编译成功；ROS 构建脚本退出码 0 |
| 安装后软件检查 | 13 项全部通过：接口、可执行文件、共享库、驱动 Launch 只解析、FAST-LIO 无输入初始化、服务图及正常退出 |
| FAST-LIO 隔离启动 | Domain 177、localhost、关闭 RViz；`/map_save` 服务可见，未调用；SIGINT 后退出码 0 |
| 真机驱动数据 | 本轮不启动，未测试；10 Hz 点云、200 Hz IMU 仅为预期 |
| 实机建图和保存 PCD | 本轮不启动，未测试 |

软件检查结束后，`dpkg --audit` 输出为空；根分区约有 21 GB 可用空间，内核为 `6.8.0-1047-raspi`。没有更改 swap。不能用旧卡 2026-11-09 的实测结果替代新卡真机验收。

依赖安装实际新增 525 个包、更新 8 个依赖包，删除 0 个包，下载约 450 MB，新增占用约 1931 MB。主要版本为 PCL `1.12.1`、Eigen `3.4.0`、APR `1.7.0`，完整包版本在验收 JSON 中。

## 版本、目录与组件的关系

| 组件 | 官方来源及锁定提交 | 本卡源码 / 安装位置 |
| --- | --- | --- |
| Livox-SDK2 | `Livox-SDK/Livox-SDK2`，`c0796f04c143143899c87a773d9f6b7136453c0b` | 源码 `~/src/Livox-SDK2`；构建 `build-pi5`；安装 `~/livox_sdk2` |
| livox_ros_driver2 | `Livox-SDK/livox_ros_driver2`，`21445540f0d100dc86a7e6df312dd70bbdb4afdf` | `~/ws_livox/src/livox_ros_driver2`；工作空间安装结果 `~/ws_livox/install` |
| FAST-LIO ROS2 | `Ericsii/FAST_LIO_ROS2`，`2fffc570a25d0df172720bac034fbdb6a13d2162` | `~/ws_fastlio/src/FAST_LIO_ROS2`；工作空间安装结果 `~/ws_fastlio/install` |
| ikd-Tree 子模块 | FAST-LIO 锁定的 `e2e3f4e9d3b95a9e66b1ba83dc98d4a05ed8a3c4` | FAST-LIO 源码内 `include/ikd-Tree` |

SDK2 负责与 MID360 通信；ROS 驱动把 SDK 数据发布为 ROS2 消息；FAST-LIO 订阅点云与 IMU，估计运动并构建内部地图。FAST-LIO 需要驱动提供的 `livox_ros_driver2/msg/CustomMsg`，所以编译和加载环境都必须先驱动、后 FAST-LIO。

本次使用两个 ROS 工作空间，避免驱动构建和算法构建相互清理。官方驱动 `build.sh` 会清理所在工作空间的构建目录，因此本次不运行它；改为复制 `package_ROS2.xml` 到 `package.xml`，并显式传入 ROS2/Humble 的 CMake 参数。

## 本次脚本做了什么

安装脚本在树莓派 `~/livox_stack_setup`，运行脚本和配置在 `~/livox_runtime`。这些是本轮针对新卡生成的文件，不能用仓库中旧卡独立恢复环境的历史 `runtime/` 脚本覆盖它们。虽然目录名相同，本卡现在使用的是系统 ROS2 Humble 和新编译的两个工作空间；旧卡曾使用的私有依赖布局不适用于这里。

| 文件 | 作用 |
| --- | --- |
| `install_dependencies.sh` | 健康状态和空间检查、备份旧配置、设置雷达专用 eth0、APT 模拟及安装依赖；需要 sudo |
| `build_sdk2.sh` | 核对 SDK 提交，单线程编译共享/静态库，安装头文件与库到 `~/livox_sdk2`；普通用户运行 |
| `configure_stack.py` | 备份上游配置，设置雷达目标地址，生成两份 FAST-LIO 配置和日志目录 |
| `build_ros_stack.sh` | 先编译驱动、加载其消息接口，再编译 FAST-LIO；普通用户运行 |
| `verify_dependencies.sh` | 复核实际安装状态、PCL 模块名和 CMake 配置；不会重新安装软件 |
| `check_headless_ready.py` | 不启动驱动，解析驱动 Launch，并在隔离环境短暂启动 FAST-LIO 以检查软件初始化 |
| `collect_software_evidence.py` | 汇总版本、状态和软件检查 JSON，不启动设备或上传凭据 |
| `env.sh` | 按 ROS2 基础环境 → 驱动 → FAST-LIO 顺序加载，设置 SDK 共享库路径与 Domain |
| `run_livox.sh` | 检查 eth0 地址和物理链路，然后启动无 Viewer 的 CustomMsg 驱动 |
| `run_fastlio.sh` | 加载默认或短时保存配置，关闭 RViz，启动 FAST-LIO |
| `verify_live_stream.py` | 将来只订阅实际话题，检查接收频率、时间戳与基础内容；不会自行启动雷达或算法 |

依赖包括 `libpcl-dev`、`libeigen3-dev`、`libapr1-dev`、`pkg-config`、`ros-humble-pcl-conversions`、`ros-humble-pcl-ros`、`ros-humble-visualization-msgs`、`ros-humble-std-srvs` 和 Python 开发依赖。PCL 转换库用于点云处理，不等于安装 Livox Viewer。

管理员脚本先模拟安装，禁止删除现有软件包，并在计划涉及内核或固件变更时停止。它不做整系统升级，不重建 dpkg 数据库，也不修改 SD 卡分区。

## eth0 和 Wi-Fi 分工

| 项目 | 本次配置 |
| --- | --- |
| MID360 地址 | `192.168.123.20`，保留设备现有地址 |
| 接收雷达数据的主机 | 树莓派 eth0：`192.168.123.4/24` |
| Wi-Fi | wlan0 继续负责 SSH 与上网 |
| 持久网口配置 | `/etc/systemd/network/05-livox-eth0.network`，只匹配 `Name=eth0` |
| 网关、DNS | eth0 不添加网关或 DNS，避免影响 Wi-Fi 默认路由 |

网络脚本采用 `networkctl reload` 重读文件，再对 eth0 单独 `reconfigure`，不重启 Wi-Fi 或整套网络服务。配置网口不等于启动雷达进程。

驱动 `MID360_config.json` 的 `cmd_data_ip`、`push_msg_ip`、`point_data_ip`、`imu_data_ip` 均为 `192.168.123.4`，`lidar_configs[0].ip` 为 `192.168.123.20`。JSON 里的主机地址必须与树莓派实际接收网口一致，不应把同一地址同时配置给同一网络中的电脑和树莓派。

实际启动的官方 `msg_MID360_launch.py` 读取驱动安装目录的 `config/MID360_config.json`；本次使用 `--symlink-install`，已经通过 `readlink` 核实它对应 `~/ws_livox/src/livox_ros_driver2/config/MID360_config.json`。`~/livox_runtime/config/MID360_config.json` 另存供查看，并非当前 Launch 的独立覆盖入口。只改这份副本不会自动修改驱动实际读取的配置。

FAST-LIO 则通过运行脚本显式读取 `~/livox_runtime/config` 中的 YAML。仓库 `configs/pi5/` 是版本记录，不是自动部署系统；在 VS Code 中修改仓库文件后，必须先检查差异，再人工同步到相应实际运行路径。`configure_stack.py` 是首次生成工具，重复运行会从上游备份重新生成配置，可能覆盖后来手动调整的参数，不能当作无损同步工具。

## SDK 与 ROS 构建命令说明

以下是本次脚本入口的记录，已经成功的步骤不必重复执行。它们均在树莓派 VS Code Remote-SSH 终端执行。

```bash
# 安装系统依赖并设置 eth0；sudo 密码只在树莓派终端输入。
sudo bash ~/livox_stack_setup/install_dependencies.sh

# 普通用户编译 SDK2，安装到 ~/livox_sdk2；不需要 sudo。
bash ~/livox_stack_setup/build_sdk2.sh

# 独立复核系统依赖；不重复安装软件。
bash ~/livox_stack_setup/verify_dependencies.sh

# 生成适合本卡的驱动 JSON 和 FAST-LIO YAML，备份上游原件。
python3 ~/livox_stack_setup/configure_stack.py

# 普通用户按依赖顺序编译驱动和 FAST-LIO。
bash ~/livox_stack_setup/build_ros_stack.sh
```

SDK 构建显式使用 `-DCMAKE_INSTALL_PREFIX=/home/xin/livox_sdk2`，只构建所需共享/静态库，再安装 `sdk_core` 的库与公开头文件。ROS 驱动 CMake 显式给出 SDK 头文件和共享库路径，不依赖 `/usr/local` 恰好有某个旧版本。

两个 ROS 构建都采用 `CMAKE_BUILD_PARALLEL_LEVEL=1`、`MAKEFLAGS=-j1` 和 `--executor sequential`。本次 FAST-LIO 最终成功的 Release C++ 参数是：

```text
-O1 -DNDEBUG --param=ggc-min-expand=10 --param=ggc-min-heapsize=32768
```

这使 GCC 更频繁地回收编译器内部内存，减少 4 GB、无 swap 设备的编译峰值；不是对运行时 10 Hz 建图性能的承诺。构建关闭本次不需要的 Rust 消息生成器，保留 ROS 的 C++/Python 消息接口。

## 本次遇到的两处问题与解决方法

### 依赖安装后的 PCL 检查命令名称不匹配

软件包安装已经完成，但首次脚本用 `pkg-config --modversion pcl_common` 检查时失败，原状态保留为 `EXIT=1`。本卡 Ubuntu Jammy 的实际模块名是 `pcl_common-1.12`，不能由该报错认定 PCL 不支持树莓派、软件包损坏或需要重装。

已把脚本改为兼容两种名称，并增加普通用户 `verify_dependencies.sh`：逐项确认包状态为 `install ok installed`、`dpkg --audit` 为空、PCL 模块版本可读取，以及 `/usr/lib/aarch64-linux-gnu/cmake/pcl/PCLConfig.cmake` 存在。复核退出码 0。原始安装日志和状态未删除，后续成功复核单独记录在 `dependencies-verified.status`，避免隐藏实际排查过程。

### FAST-LIO 首轮编译器被系统终止

驱动首轮编译成功，用时约 1 分 16 秒。FAST-LIO 首次采用 `-O2` 单线程编译 `laserMapping.cpp` 时，编译器占用升至约 2.7 GB，系统可用内存降至约 372 MB，随后出现 `cc1plus` 被 `Killed`、构建退出码 2。结合内存观测，按编译内存不足处理；这不是雷达输入或标定错误。

首轮日志保留为 `~/livox_stack_setup/build-ros-stack-o2-failed.log`。不修改系统 swap 或内核，改用上面的 `-O1` 与 GCC 回收参数，第二轮编译成功。实机吞吐、建图延迟和长期内存占用需待接入雷达后测量。

## 环境和 FAST-LIO 配置

```bash
# 在每个将要操作这套雷达软件的终端，先加载本卡新环境。
source ~/livox_runtime/env.sh

# 核对三个包是否能被找到；只查询，不启动雷达。
ros2 pkg prefix livox_ros_driver2
ros2 pkg prefix fast_lio

# 核对 FAST-LIO 所需的点云消息定义；只查询。
ros2 interface show livox_ros_driver2/msg/CustomMsg
```

环境脚本按基础 ROS2、驱动、FAST-LIO 三层加载，并把 `/home/xin/livox_sdk2/lib` 放入 `LD_LIBRARY_PATH`。默认 `ROS_DOMAIN_ID=10`、`ROS_LOCALHOST_ONLY=0`、`RMW_IMPLEMENTATION=rmw_fastrtps_cpp`。若后续让电脑加入 ROS2 通信，需要双方 Domain、发现方式、消息类型和 QoS 匹配，不能只凭相同 Domain 认定已互通。

若确实需要更改 Domain，应在两个终端加载前统一设置，不能只改其中一端：

```bash
# 示例仍为本次默认域10；有明确通信方案时再改数值。
export LIVOX_ROS_DOMAIN_ID=10
source ~/livox_runtime/env.sh
```

FAST-LIO 输入是 `/livox/lidar`（CustomMsg）与 `/livox/imu`（sensor_msgs/Imu）。MID360 配置基于上游 `mid360.yaml`：`lidar_type=1`、`scan_line=4`、`scan_rate=10`、`timestamp_unit=3`、`time_sync_en=false`、时间偏移 `0.0`。配置关闭在线外参估计，使用上游 MID360 内置 IMU 外参：平移 `[-0.011, -0.02329, 0.04412]`，旋转为单位矩阵。这是采用上游给定值，并未重新进行实测标定。

| 配置 | 默认运行 `mid360_pi5.yaml` | 短时保存 `mid360_pi5_save.yaml` |
| --- | --- | --- |
| `publish.map_en` | false | true |
| `publish.path_en` | false | true |
| `pcd_save.pcd_save_en` | false | true |
| `runtime_pos_log_enable` | false | false |
| 地图保存路径 | `~/livox_runtime/maps/mid360_map.pcd` | 同左 |

默认关闭额外的整图、轨迹与 PCD 累积，保留单帧注册点云和里程计；FAST-LIO 算法自身仍需要维护内部地图。短时保存模式会累积整图，不适合长时间常驻采集。

上游即使关闭 `runtime_pos_log_enable`，仍会在源码 `~/ws_fastlio/src/FAST_LIO_ROS2/Log` 打开部分日志文件。配置脚本保留该可写目录和 `PCD` 目录。运行目录中的 `logs/` 不是所有上游日志的统一输出位置；监测 SD 卡空间时应同时查看源码 `Log/`，不能声称已关闭全部磁盘写入。

## 待用户通知后：两终端运行与真机验收

下面只记录后续步骤，本轮不执行。确认 MID360 供电和网线接到 eth0，并核对地址、路由与物理链路后，再启动。最初静止放置数秒，供 IMU 初始化。

终端一运行驱动，保持终端开启：

```bash
# 脚本会自行加载环境；使用 CustomMsg，无 Viewer。
bash ~/livox_runtime/run_livox.sh
```

终端二运行 FAST-LIO，保持终端开启：

```bash
# 默认不累积整图或PCD，不打开RViz窗口。
bash ~/livox_runtime/run_fastlio.sh
```

第三终端可进行实收检查：

```bash
# 检查工具需要先加载消息接口和共享库环境。
source ~/livox_runtime/env.sh

# 先单独验收驱动：预热5秒、统计30秒，保存本次结果。
python3 ~/livox_stack_setup/verify_live_stream.py --input-only \
  --output ~/livox_runtime/logs/driver-live-result.json

# 同时启动FAST-LIO后，检查输入与注册点云/里程计输出。
python3 ~/livox_stack_setup/verify_live_stream.py \
  --output ~/livox_runtime/logs/fastlio-live-result.json
```

驱动预期点云约 10 Hz、IMU 约 200 Hz；这些数值在本轮还不是实测结果。算法应连续输出非空 `/cloud_registered` 和有效 `/Odometry`。能看到话题名、发布端或“Node init finished”只证明接口或初始化状态，不能代替实收消息、时间戳、内容和频率检查；这些检查也不等于建图精度和长期稳定性验收。

## 待用户通知后：短时 PCD 保存检查

停止默认 FAST-LIO 实例后，改用短时保存模式，不要同时启动两个算法实例：

```bash
# 开启整图缓存供保存，建议每次仅运行60–120秒。
bash ~/livox_runtime/run_fastlio.sh --save-map
```

另一个已加载环境的终端，在收到实际注册点云后执行：

```bash
# 只查询服务与类型；本身不保存地图。
ros2 service list -t

# 请求算法把当前缓存地图写为PCD，返回值需结合文件内容判断。
ros2 service call /map_save std_srvs/srv/Trigger '{}'
```

`/map_save` 是服务，不是话题；节点创建该服务不代表缓存里已有地图。保存模式需要相关整图与 PCD 设置配合；默认配置不应被用来证明整图保存成功。保存调用完成后，除了检查返回状态，还要确认文件存在且 PCD 的 `POINTS` 大于零：

```bash
# 只读解析PCD头，不把二进制点云当文本打印。
python3 - <<'PY'
from pathlib import Path
pcd = Path.home() / 'livox_runtime/maps/mid360_map.pcd'
points = None
with pcd.open('rb') as stream:
    for _ in range(64):
        line = stream.readline()
        if line.startswith(b'POINTS '):
            points = int(line.split()[1])
        if line.startswith(b'DATA '):
            break
print(f'PCD={pcd} BYTES={pcd.stat().st_size} POINTS={points}')
assert points is not None and points > 0, '地图点数为空，不能认定保存成功'
PY
```

检查完成后，按 Ctrl+C 正常结束 FAST-LIO，再结束驱动。短时保存模式的退出过程还可能产生上游 `PCD/scans.pcd` 等文件，注意实际输出位置和空间。PCD、原始话题数据、构建产物和软件包不上传源码仓库。

## 软件检查、日志与后续验收边界

本轮软件检查使用以下命令，驱动的 `--show-args` 只解析启动文件，不启动驱动 Node。检查器短暂启动 FAST-LIO 时采用独立 Domain 177 和本机通信范围，不接收真实雷达数据；运行环境的默认 Domain 10 保持独立。

```bash
# 先加载已编译的两层工作空间与SDK库路径。
source ~/livox_runtime/env.sh

# 软件检查会短暂启动无输入FAST-LIO，随后正常停止；不会启动驱动。
python3 ~/livox_stack_setup/check_headless_ready.py

# 汇总现有状态与检查结果为软件准备JSON，不启动雷达。
python3 ~/livox_stack_setup/collect_software_evidence.py
```

```bash
# 查询管理员依赖安装、SDK与ROS构建的状态，不启动雷达。
cat ~/livox_stack_setup/dependencies.status
cat ~/livox_stack_setup/dependencies-verified.status
cat ~/livox_stack_setup/sdk2.status
cat ~/livox_stack_setup/ros-stack.status

# 核对本卡的包数据库；健康状态应无输出。
dpkg --audit
```

`dependencies.status` 中保留的首次 `EXIT=1` 对应前述 PCL 检查名称问题；后续应结合 `dependencies-verified.status` 的 `EXIT=0` 和实际包状态判断，不能孤立解释为安装失败。SDK、最终 ROS 构建及软件检查均已通过，13 项结果及日志路径见仓库的验收 JSON。

真机启动、消息频率、建图输出、地图点数与长期稳定性继续明确标记为未测试，直到用户通知并完成对应验收。`/map_save` 本轮只检查服务图中可见，从未调用，也没有生成实机地图。

认证信息不属于本记录：不复制私人密钥，不记录密码或 GitHub 令牌，也不把授权文件或会话凭据放入 Git。
