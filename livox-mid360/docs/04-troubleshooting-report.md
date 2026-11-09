# 树莓派 MID360 驱动故障排查与解决报告

**日期：2026 年 11 月 9 日**

**目标：在现有树莓派系统中运行 `livox_ros_driver2`，实际接收 MID360 点云和 IMU，同时保留原工作区与系统配置。**

## 1. 最终结果

树莓派已完成真实雷达采集和 ROS2 消息发布。使用最终安装目录中的驱动启动雷达，预热 5 秒后连续统计 25 秒，结果如下。

| 检查项目 | 实测结果 |
| --- | --- |
| 点云话题 | `/livox/lidar` |
| 点云类型 | `livox_ros_driver2/msg/CustomMsg` |
| 点云接收量 | 250 帧 |
| 点云接收频率 | **10.0002 Hz** |
| 每帧点数 | 19,872～20,160 点 |
| 检查过的点坐标数量 | 4,999,776 个点 |
| IMU 话题 | `/livox/imu` |
| IMU 类型 | `sensor_msgs/msg/Imu` |
| IMU 接收量 | 5,001 条 |
| IMU 接收频率 | **199.994 Hz** |
| 数据检查 | 点数与数组长度一致，坐标为有限值，消息时间戳递增，点云 `timebase` 非零，IMU 六轴值均为有限值 |
| 错误计数 | 点云 0，IMU 0 |
| 检查器结果 | `passed: true` |
| 停止测试 | SIGINT 后正常退出，SDK 完成释放，无测试驱动进程残留 |

本次成功范围是**树莓派连接真实 MID360、接收数据并在树莓派本机发布 ROS2 消息**。电脑通过 Wi-Fi 订阅、FAST-LIO 建图、长期稳定运行和传感器标定不属于此次已完成的验证。

## 2. 实际使用的环境和地址

| 项目 | 配置 |
| --- | --- |
| 设备 | 用户的树莓派 5，约 4 GB 内存 |
| 操作系统 | Ubuntu 22.04.5 LTS |
| 处理器架构 | `aarch64` / ARM64 |
| ROS2 | Humble |
| 驱动 | Livox ROS Driver2 1.2.8 |
| SDK | 官方 Livox SDK2 源码重新构建，版本函数返回 1.5.2 |
| ROS 中间件 | `rmw_fastrtps_cpp` |
| ROS 域 | `ROS_DOMAIN_ID=10` |
| 原工作区 | `/home/xin/ws_livox` |
| 最终独立运行目录 | `/home/xin/livox_runtime` |

| 网络角色 | 地址 | 用途 |
| --- | --- | --- |
| MID360 雷达 | `192.168.123.20` | 雷达设备本身 |
| 树莓派 `eth0` | `192.168.123.4/24` | 接收雷达数据的有线网口 |
| 树莓派 `wlan0` | 本次为 `192.168.0.103` | SSH 远程维护；不是雷达数据输入网口 |

**`192.168.123.20` 是雷达地址，`192.168.123.4` 是树莓派接收端地址，两者不能混用。** 本次最终 JSON 中，`lidar_configs[].ip` 为 `.20`，各个 `host_net_info` 接收 IP 为 `.4`。

## 3. 出了哪些问题，分别怎么解决

### 3.1 最初找不到 PCL，普通安装流程又被损坏的包管理环境阻断

最初编译报错：

```text
Could not find a package configuration file provided by "PCL"
PCLConfig.cmake
pcl-config.cmake
```

这表示 CMake 没有找到 PCL 开发包，**不能据此判断 PCL 不支持树莓派或 ARM64**。

正常情况下可以安装 `libpcl-dev`。但此前执行 APT 安装时，又陆续出现索引无法解析、DEB 归档无效，以及：

```text
dpkg: error: too-long line or missing newline in '/var/lib/dpkg/triggers/File'
```

检查发现，该触发器文件内容已经不是正常文本。磁盘剩余空间约 22 GB，inode 使用率约 7%，因此当时的错误不能归因于磁盘空间或 inode 耗尽。

实际采用的办法是核查驱动是否真的需要 PCL。当前 ROS2 的 CustomMsg、PointCloud2、IMU 发布路径没有使用 PCL 算法。原工作区在本轮直接接管前已经存在去除这部分 PCL 依赖的调整，本轮沿用并核验了这些调整，随后在隔离源码副本中进一步去掉未使用的 APR 构建依赖及相关清单项。

因此，最终成功路径**没有依靠修好 APT 后安装完整的 `libpcl-dev`**。它保留了目标 ROS2 发布能力，避免安装目标路径没有使用的大型依赖。这个结论只适用于此次核查过的驱动路径，不能推广到其他依赖 PCL 的程序。

### 3.2 后续发现 ROS、SDK 和编译环境也有已有文件损坏

继续构建时发现，问题超过了缺少一个开发包的范围。

| 发现 | 具体证据 | 造成的影响 |
| --- | --- | --- |
| ROS CMake 文件损坏 | `python_cmake_module`、`rclcpp_components`、部分 ament 文件出现异常字节或解析错误 | CMake 无法完成配置 |
| ROS Python 文件损坏 | `rosidl_parser` 等报 `source code string cannot contain null bytes`，部分模块出现 UTF-8 解码错误 | 消息接口代码无法生成或模块无法导入 |
| ROS 动态库损坏 | 多个核心 `.so` 文件无法识别为有效 ELF，包括部分 `rclcpp`、`rcl`、Fast DDS 相关库 | 即使编译完成，也无法可靠加载运行 |
| 原 Livox SDK 损坏 | 已安装的 `.so`、`.a` 不能正常识别；原 SDK 源码中也有大量异常文本 | 无法直接复用 SDK 库或原源码构建 |
| 现有编译环境不可用 | `cc1plus` 出现 `Illegal instruction`，标准 C++ 头文件出现异常字节 | 简单 C++ 编译也会失败 |
| Python 数值依赖损坏 | 原 NumPy 扩展、BLAS 库等出现无效 ELF 文件头 | Python 消息支持或检查工具无法正常导入 |

此前内核日志还有：

```text
mmc0: Card stuck being busy!
```

这是存储访问异常的线索，但**尚不能确定 SD 卡存在物理损坏，也不能确定这些文件损坏由 SD 卡、供电还是其他原因造成**。此次没有完成硬件和文件系统根因鉴定。

解决方式是建立用户目录下的独立环境：

1. 从官方 ROS、Ubuntu 软件源获取所需 ARM64 软件包，并按软件包索引中的 SHA256 校验下载内容。
2. 将软件包解压到 `/home/xin/livox_runtime` 内的私有目录，不经过系统 dpkg 安装。
3. 使用独立的干净 GCC、标准头文件及编译所需库，绕开原来不可用的编译环境。
4. 从官方获取干净的 Livox SDK2 源码，重新构建共享库，安装到用户目录。
5. 使用干净的 ROS 依赖和新 SDK 编译驱动，再验证最终程序的动态库加载路径。

最终驱动和检查器的依赖检查均未发现 `not found`，运行时没有依赖 `/dev/shm` 中的临时库。

**这次解决的是驱动的独立运行环境；原系统的 APT/dpkg、ROS 和 SDK 损坏文件仍然保留，没有被整体修复。**

### 3.3 colcon 功能不完整，部分常见命令无法使用

树莓派上的 colcon 缺少部分扩展，曾出现：

```text
invalid choice: 'list'
unrecognized arguments: --packages-select livox_ros_driver2
```

这属于构建工具扩展缺失，不能据此判断驱动包本身无效。此次构建使用当前工具支持的 `--base-paths` 直接指定驱动源码，并明确设置：

```text
ROS_EDITION=ROS2
DISTRO_ROS=humble
CMAKE_BUILD_TYPE=Release
BUILD_TESTING=OFF
```

同时禁用本次不需要的符号链接安装和 Rust 消息生成路径，减少对已有损坏文件的依赖。最终完整编译并安装了目标驱动及其消息接口。

### 3.4 网络地址曾丢失，接着又遇到有线物理链路未建立

检查网络时发现，此前临时添加的 `eth0` 地址没有保留下来。恢复以下地址后，发往雷达的路由已正确走有线网口：

```bash
# 启用树莓派有线网口
sudo ip link set eth0 up

# 为雷达网口配置接收地址，不添加默认网关
sudo ip address replace 192.168.123.4/24 dev eth0
```

但当时仍然无法 ping 通雷达。进一步检查显示：

```text
eth0: NO-CARRIER
/sys/class/net/eth0/carrier = 0
```

这表示网口没有检测到物理链路。仅设置 IP 或修改 ROS 配置不能解决这个状态，需要检查雷达供电、数据网线和接线位置。

用户接好雷达后，状态变成 `UP/LOWER_UP`、`carrier=1`，并成功 ping 通 `192.168.123.20`，3 次请求全部收到回复。随后驱动才能控制雷达进入 Normal 状态并取得真实数据。

这个过程也说明：**SDK 初始化成功，只能证明软件初始化完成，不能证明已经收到雷达点云。**

### 3.5 没有雷达数据时，驱动按 Ctrl+C 会卡住

在尚未建立物理链路时进行启动测试，驱动能够完成初始化，但 SIGINT 后没有正常结束，受控测试最终需要强制终止。

源码检查确认：点云和 IMU 工作线程分别阻塞在信号量等待中。原来的退出流程设置了退出标志，却没有唤醒这两个线程，主线程随后在 `join()` 等待它们结束。

在独立源码副本中进行了以下修改：

- 先让退出通知生效，再请求数据源退出。
- 主动唤醒点云和 IMU 的信号量，使等待线程能够检查退出条件。
- 在线程指针有效且 `joinable()` 时再等待线程结束。
- 将退出标志从 `volatile bool` 改为 `std::atomic<bool>`，使跨线程访问有明确的同步语义。
- 在点云发布循环中检查退出标志，避免持续有数据时延迟退出。

重新编译后，在无数据和真实数据测试中都验证了正常退出。最终日志包含：

```text
signal_handler(SIGINT/SIGTERM)
Livox Lidar SDK Deinit completely!
```

这些修改只存在于 `/home/xin/livox_runtime/src/livox_ros_driver2` 等本次任务副本中，原工作区源码未被覆盖。

### 3.6 第一次检查频率偏低，实际是 Python 检查器处理大消息的瓶颈

第一次真实数据检查采用单线程 Python 订阅器。每帧 CustomMsg 包含约 2 万个点，转换成大量 Python 点对象会占用较多处理时间，并连带阻塞 IMU 回调。

当时观测到点云约 `7.136 Hz`、IMU 约 `7.268 Hz`。这个结果**不能直接解释为雷达实际只输出约 7 Hz**。

为区分驱动发布问题和检查器处理开销，编译了原生 C++ 检查器，保持原来的频率通过门槛，不通过降低门槛来宣布成功。新检查器仍逐帧检查点数，遍历接收到的点检查坐标，并逐条检查 IMU。

新检查器先预热 5 秒，排除驱动启动阶段的积压，再统计 25 秒，最终测得点云 `10.0002 Hz`、IMU `199.994 Hz`，检查通过。

现在 `verify_livox_stream.py` 只是调用原生 C++ 程序的入口，不再在 Python 中逐点解析。日后检查此类密集 CustomMsg 时，应优先使用这个工具；普通 `ros2 topic hz /livox/lidar` 也可能因 Python 解析开销而测得偏低频率。

## 4. 最终安装在哪里，改了什么

```text
/home/xin/livox_runtime/
├── run_livox.sh                 # 驱动启动脚本
├── env.sh                       # 当前终端使用的独立 ROS 环境
├── config/MID360_config.json    # 实际启动脚本读取的雷达配置
├── install/livox_ros_driver2/   # 编译完成的驱动和消息接口
├── sdk/                         # 重新编译的 SDK 库及头文件
├── ros-clean/                   # 私有 ROS 依赖
├── ubuntu-clean/                # 私有系统依赖
├── python-clean/                # 必要的 Python 依赖
├── src/livox_ros_driver2/        # 本次修改后的驱动源码副本
├── bin/verify_livox_stream      # 原生 C++ 检查器
├── verify_livox_stream.py       # 调用原生检查器的 Python 入口
├── validation/                  # 构建、启动、实际数据检查记录
└── rebuild/                     # 本次构建命令与源码差异留档
```

操作中保留了 Windows、虚拟机的网络设置和树莓派原工作区；没有覆盖系统 `/opt/ros`、`/usr/local`，没有重建 dpkg 数据库，也没有格式化或重刷 SD 卡。原工作区的 146 个文件与接管前备份逐一 SHA256 比较，全部一致。

编译使用单线程，在 `/dev/shm` 内存目录中生成大部分中间文件，以减少 SD 卡编译写入；最终运行文件安装到持久用户目录。**重启后运行程序不需要重新编译。** 留档的重建脚本仍依赖本次 RAM 工具链等前置环境，不能理解为重启后可直接执行的一键重建脚本。

`env.sh` 会在当前终端设置 Fast DDS、域 ID 10，加载独立依赖，并清理旧 Discovery Server/XML 环境变量；它不修改 `.bashrc`。此次没有设置开机自启。

## 5. 以后如何启动和复查

以下命令都在树莓派终端执行。

### 5.1 启动驱动

确保雷达已供电，数据网线连接树莓派有线网口，然后执行：

```bash
# 脚本会加载独立环境并检查 eth0 地址和物理链路
bash ~/livox_runtime/run_livox.sh
```

看到驱动运行后保持该终端打开，按 **Ctrl+C** 停止。该脚本发布 ROS 消息，不录制 rosbag 或保存完整点云文件。

### 5.2 检查点云和 IMU

在驱动保持运行的情况下，另开一个树莓派终端：

```bash
# 让当前终端能找到独立安装的驱动、消息类型和依赖
source ~/livox_runtime/env.sh

# 预热 5 秒，随后同时检查 25 秒点云和 IMU
python3 ~/livox_runtime/verify_livox_stream.py
```

结果中应看到点云约 10 Hz、IMU 约 200 Hz，且 `passed` 为 `true`。只有接收到真实消息并完成检查，才算这条采集链路通过。

### 5.3 重启后连接不上雷达

本次设置的是临时有线地址。如果重启后地址丢失，执行：

```bash
# 恢复雷达专用网口地址，不改 Wi-Fi
sudo ip link set eth0 up
sudo ip address replace 192.168.123.4/24 dev eth0

# 查看地址、物理链路和发往雷达的路由
ip -br -4 addr show eth0
cat /sys/class/net/eth0/carrier
ip route get 192.168.123.20

# 测试雷达连接
ping -c 3 192.168.123.20
```

`carrier=0` 时检查供电和接线；`carrier=1` 但仍不通时，再检查地址、路由和设备状态。网口配置恢复后，按前面的命令启动即可。

### 5.4 修改雷达配置

实际运行配置为：

```text
/home/xin/livox_runtime/config/MID360_config.json
```

修改这个 JSON 后需要保存文件，停止并重新启动驱动；**只修改 JSON 不需要重新编译**。不要只改原工作区的同名文件而误以为启动脚本会自动读取它。

## 6. 备份和可追溯记录

本次现场的 Windows 归档目录形式为（该目录中的大文件未加入此仓库）：

```text
<Windows用户目录>\livox-project-review
```

| 文件 | 内容 |
| --- | --- |
| `pi-source-backup-20261109.tar.gz` | 本轮直接操作前的原工作区源码及配置备份 |
| `pi-validated-runtime-20261109.tar.gz` | 已通过真实采集验证的完整独立运行环境，包含 SDK、私有依赖、驱动、检查器和验证结果 |
| `validation-report.md` | 简要验证记录 |
| `README-livox.md` | 日常启动与使用说明 |
| 本文档 | 问题、诊断依据和解决过程说明 |

原始源码备份 SHA256：

```text
165fe1878ffdbf092836783cba32284eb760d07fa47615c46adced7e48676822
```

最终运行环境备份大小为 **29,716,684 字节**，SHA256：

```text
5a0da32324bd362008b7dfa02b2728069b4dc51921c01f46e41750f03a7ba46e
```

已打开最终归档并核对其中的真实验证结果与原生检查器。恢复包使用当前树莓派的绝对路径布局，适合恢复到同一用户路径，不能视作可直接用于其他操作系统或架构的通用安装包。

驱动源码基于 commit `21445540f0d100dc86a7e6df312dd70bbdb4afdf`；重新构建的官方 SDK2 源码 commit 为 `c0796f04c143143899c87a773d9f6b7136453c0b`。修改差异保存在运行目录的 `rebuild/task-changes.patch`。

配置结束后，已精确移除树莓派上的本次临时 SSH 公钥，并验证该密钥无法再登录；本机临时私钥和公钥文件也已删除。

## 7. 尚未解决或未验证的事项

- **原系统损坏仍在。** 此次通过独立目录恢复驱动运行，没有修好原 APT/dpkg、原 ROS、原 SDK 文件；以后使用原环境安装软件或运行其他程序仍可能遇到已有问题。
- **SD 卡和供电根因未确定。** 驱动现在能跑，不代表已经证明 SD 卡、供电或文件系统完全健康。
- **跨机器传输尚未验证。** 本次本地采集成功，不能直接等同于虚拟机已经通过 Wi-Fi 收到这些数据；电脑侧仍需验证一致的 ROS 域、发现方式和网络路径。
- **建图与长期运行尚未验证。** 25 秒的真实数据测试确认了当前采集能力，不代表已完成 FAST-LIO 建图、外参标定或长期零丢包测试。
