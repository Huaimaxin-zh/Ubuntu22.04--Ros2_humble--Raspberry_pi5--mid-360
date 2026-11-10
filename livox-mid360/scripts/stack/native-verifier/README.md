# MID360 / FAST-LIO 原生实收验收器

这是针对树莓派5、ROS2 Humble 和 `livox_ros_driver2` 编写的 C++ 验收工具。它只订阅已经运行的话题并写入结构化 JSON，不启动或关闭雷达，不调用地图保存服务。文件中的中文注释解释各项检查与计算。

早期 Python 检查在同时处理点云和 IMU 时产生明显 CPU 负载，影响接收计数。最终主验收流程采用此工具，避免把观察器处理不过来误判为驱动发布速率不足。它验证短时实收数据的基础格式、数值与时间关系，不验证建图精度、外参标定、闭环或长期稳定性。

## 准备与构建

以下命令均在树莓派 `xin` 的 Bash 终端执行。需要先完成 ROS2、驱动及 SDK 的安装，并把本目录源码放在 `~/livox_stack_setup/native-verifier`。构建产物写入这个目录下的 `build`，不修改驱动或 FAST-LIO 源码。

```bash
# 从Git仓库复制源码目录；仓库不包含build或二进制。
mkdir -p ~/livox_stack_setup
cp -r ~/projects/raspberrypi-mid360/livox-mid360/scripts/stack/native-verifier \
      ~/livox_stack_setup/

# 加载 ROS2、驱动消息和 SDK 共享库路径。
source ~/livox_runtime/env.sh

# 配置这个小型验收程序的独立构建目录；不会启动雷达。
cmake -S ~/livox_stack_setup/native-verifier \
      -B ~/livox_stack_setup/native-verifier/build \
      -DCMAKE_BUILD_TYPE=Release

# 单线程编译，降低树莓派构建时的内存压力。
cmake --build ~/livox_stack_setup/native-verifier/build --parallel 1
```

依赖为 `ament_cmake`、`rclcpp`、`livox_ros_driver2`、`sensor_msgs` 和 `nav_msgs`。使用 C++17，并对本检查程序启用 `-O2 -Wall -Wextra`；这一选项与 FAST-LIO 本次采用的 `-O1` 编译配置无关。

## 运行方法

驱动和算法应先在其他终端正常运行。单独调用此程序只观察现有数据；它不会为缺失的话题自行启动节点。默认先预热 5 秒，再统计 30 秒。结果文件写到明确指定的路径。

```bash
# 当前终端加载同一 ROS_DOMAIN_ID 及消息接口。
source ~/livox_runtime/env.sh

# 只检查驱动：CustomMsg 点云和 IMU。
~/livox_stack_setup/native-verifier/build/verify_live_stream_native \
  --input-only --output ~/livox_runtime/logs/input-check.json

# 驱动和 FAST-LIO 都运行后，检查四路输入/输出。
~/livox_stack_setup/native-verifier/build/verify_live_stream_native \
  --output ~/livox_runtime/logs/mapping-check.json
```

可选参数：`--duration 30` 指定统计秒数，`--warmup 5` 指定预热秒数，`--scan-lines 4` 指定允许的线号数量。输出路径必填。标准完整验收由上一级的 `run_live_acceptance.py` 负责启动节点、分三个阶段调用此程序、保存地图并停止自己创建的节点；完整 runner 不应与用户已有驱动/算法实例同时运行。

## 检查内容

| 流 | 默认最低实收速度 | 基础数据检查 |
| --- | --- | --- |
| `/livox/lidar`，CustomMsg | 5 Hz | 点数非零、`point_num` 与数组长度一致、全部 XYZ 有限、线号在 0～3 |
| `/livox/imu`，Imu | 100 Hz | 三个角速度与三个加速度数值有限；记录加速度模长但不强制其等于 9.81 |
| `/cloud_registered`，PointCloud2 | 3 Hz | 字段和 payload 布局有效，按偏移与字节序抽取每帧最多 512 个 XYZ，检查有限和非零 |
| `/Odometry`，Odometry | 3 Hz | 位置及四元数有限，四元数模长与 1 的差不超过 0.01 |

阈值用于发现明显缺流，不等于期望发布频率。最终报告填写实际统计值；10 Hz/200 Hz 的配置或预期不能代替实收数值。

各话题均检查：正数时间戳、无倒退或重复、类型正确且恰有一个发布者。时间对齐使用最近时间戳，检查 lidar→imu、cloud→lidar、odom→cloud 的最大差是否不超过 0.25 秒。订阅使用 SensorDataQoS、深度 20 和单线程 executor。

JSON 中的 `received_hz` 是统计窗口内消息数除以实际统计时间；`arrival_span_hz`、`header_span_hz` 分别按到达时间跨度和消息头时间跨度计算。应结合三者判断，不把它们当成同一个量。JSON 还保留计数、基础几何统计、发布者、时间对齐和错误列表，`observer` 标注为 `native_cpp`。

工具不保留原始消息或完整点数组。本仓库仅上传小型验收结果，不上传原始点云、PCD、rosbag、日志、二进制及构建目录。

## 按顺序读懂源码

打开 [`src/verify_live_stream.cpp`](src/verify_live_stream.cpp) 后，可以按下面顺序对照阅读。这里解释数据怎样流动；实际语句与分支以留档源码为准。

| 代码位置或名称 | 逐步含义 |
| --- | --- |
| `#include` 与 `using Clock` | 引入 ROS 消息和 C++ 工具；统计窗口采用单调时钟，不因系统时间校准而突然跳动 |
| `json_quote`、`number`、`boolean` | 把字符串、数字、真假值安全写入 JSON；无效的浮点统计值输出 `null` |
| `Options` | 保存命令行选项，默认预热 5 秒、测量 30 秒、4 条扫描线 |
| `Stream::receive` | 每收到一条消息就加计数，把 `sec × 10⁹ + nanosec` 合成纳秒时间戳，并记录无效、重复或倒退 |
| `Stream::points`、`xyz` | 记录点数上下限；检查坐标是否为有限数，并累计非零坐标数量 |
| `Stream::rate`、`passed` | 以计数除以实际测量秒数计算速度，再结合最低速度、时间戳、内容和发布者检查决定这一流是否通过 |
| `coordinate` | 按 PointCloud2 的字段偏移和 FLOAT32/FLOAT64 定义复制坐标；需要时调整字节序，避免直接把未对齐字节当浮点数 |
| `Alignment` | 对另一流的时间戳排序，为每个时间戳寻找最近对应值，检查最大差是否在 0.25 秒内 |
| `main` 的参数解析 | 校验输出路径、秒数和扫描线数；有非法参数时以退出码 2 结束，不执行测量 |
| 四个订阅回调 | 收到消息时先判断是否已进入统计窗口，再分别检查点云、IMU、注册点云或里程计 |
| 预热与测量循环 | 预热消息会接收但不计入结果；循环结束后查询发布者信息、汇总流和时间对齐检查 |
| JSON 写入和退出码 | 输出小型统计文件；成功为 0，数据检查或运行失败为 1；JSON 的 `passed` 还需结合主 runner 的节点退出结果判断 |

例如某个完整统计窗口恰为 30 秒且收到 300 帧，`received_hz = 300 ÷ 30 = 10`。第一帧到最后一帧只有 299 个间隔，所以跨度速度采用 `(count - 1) ÷ span`，不能直接用 300 除以这段跨度。这个例子用于理解公式，不是替代本次实测结果。
