# 启动脚本和检查器逐条讲解

本目录中的主要代码已加入中文注释。阅读顺序建议为 `runtime/run_livox.sh` → `runtime/env.sh` → `runtime/verify_livox_stream.py` → `tools/stream_verifier/verify_livox_stream.cpp`。

## 1. Bash 的基础符号

| 写法 | 意义 |
| --- | --- |
| `# 注释` | 解释说明，不执行 |
| `root=/某个目录` | 给变量赋值，等号两边不能有空格 |
| `$root`、`${root}` | 取出变量的值 |
| `"$root/文件"` | 展开变量并保持整个路径为一个参数，避免空格拆分 |
| `source 文件` | 在当前 shell 中执行环境设置 |
| `export 名称=值` | 将变量传给后续启动的子程序 |
| `unset 名称` | 清除当前 shell 中的变量，不删除磁盘文件 |
| `命令1 \| 命令2` | 把命令1输出送给命令2 |
| `$(命令)` | 运行命令，并将它的输出作为字符串使用 |
| `if ...; then ...; fi` | 根据命令成功或失败决定是否执行一段代码 |
| `! 命令` | 对命令的成功/失败结果取反 |
| `>&2` | 把输出写到标准错误 |
| `2>/dev/null` | 不显示这一条命令的标准错误 |
| `exit 2` | 结束脚本，向调用者返回非零状态 |
| 行末 `\` | 这条命令还没写完，接下一行 |
| `exec 程序` | 用目标程序替换当前脚本进程 |
| `"$@"` | 保留调用脚本时追加的所有参数及其边界 |

## 2. run_livox.sh 按执行顺序解释

源码：[runtime/run_livox.sh](../runtime/run_livox.sh)。

| 执行内容 | 原因 |
| --- | --- |
| `#!/usr/bin/env bash` | 指定 Bash 解释器 |
| `set -e` | 普通命令失败时结束，避免环境没加载好却继续启动 |
| `root=/home/xin/livox_runtime` | 保存此次运行环境绝对路径 |
| `source "$root/env.sh"` | 加载私有 ROS、SDK 和消息接口环境 |
| `ip -o -4 addr show eth0` | 一行一个地址，列出 eth0 的 IPv4 地址 |
| `grep -q 'inet 192.168.123.4/24'` | 检查有没有雷达接收地址，不打印匹配文本 |
| 地址不匹配时打印命令并 `exit 2` | 给出明确修复提示；脚本自己不执行 sudo |
| `cat /sys/class/net/eth0/carrier` | 读取网口物理链路状态 |
| `carrier` 不为 1 时停止 | 网线或供电有问题时，不把空等误当成功 |
| `exec .../livox_ros_driver2_node` | 启动已经编译的官方驱动节点 |

最后一条启动命令中的参数：

| 参数 | 此次值 | 用途 |
| --- | --- | --- |
| `--ros-args` | 无额外值 | 后面的参数由 ROS2 解析 |
| `-r __node:=...` | `livox_lidar_publisher` | 设置节点名 |
| `-p xfer_format:=...` | `1` | 使用 Livox CustomMsg 点云格式 |
| `-p multi_topic:=...` | `0` | 使用统一话题，而非按雷达拆分 |
| `-p data_src:=...` | `0` | 使用真实雷达数据输入 |
| `-p publish_freq:=...` | `10.0` | 设置点云发布频率为 10 Hz |
| `-p output_data_type:=...` | `0` | 输出到 ROS；当前驱动声明并读取此参数，本次不录制 rosbag |
| `-p frame_id:=...` | `livox_frame` | 给消息 header 使用的坐标系名称 |
| `-p user_config_path:=...` | 运行目录的 JSON | 选择实际雷达和接收地址配置 |
| `"$@"` | 调用者传入参数 | 将附加参数继续传给驱动 |

修改 IP 时要让网口地址检查和 JSON 中的接收端地址一致。改 `frame_id` 只改变消息坐标系标签，不会自动标定外参或创建 TF。

## 3. env.sh 按执行顺序解释

源码：[runtime/env.sh](../runtime/env.sh)。

1. 保存运行目录的路径。
2. 清除旧的 ROS、CMake、colcon、Python、动态库搜索路径。
3. 加载私有 ROS 的 `local_setup.bash`。
4. 加载 Livox 驱动包的 `local_setup.bash`。
5. 在 Python 搜索路径前面放入私有依赖目录。
6. 在动态库搜索路径前面放入 SDK 和必要系统库目录。
7. 指定 `rmw_fastrtps_cpp`，ROS 域设为 10，允许使用非回环接口。
8. 清除旧 Discovery Server/XML 环境变量，回到此次验证过的本地采集配置。
9. 清除脚本内部临时变量。

`source` 和 `bash` 的区别：

```bash
# 设置会保留在当前终端，后续 ros2 命令可使用它。
source ~/livox_runtime/env.sh

# 只在子进程里设置，结束后不能改变父终端，所以不应这样加载环境。
bash ~/livox_runtime/env.sh
```

环境变量只改变当前终端及其子进程，不会修改其他已运行终端、删除 ROS 安装或写入 `.bashrc`。跨电脑使用 Discovery Server 时，需要在加载这个文件后另行设置一致的发现配置。

## 4. Python 检查入口逐行解释

源码：[runtime/verify_livox_stream.py](../runtime/verify_livox_stream.py)。

| 代码 | 含义 |
| --- | --- |
| 文档字符串 `"""..."""` | 说明文件用途 |
| `from pathlib import Path` | 导入跨平台路径操作工具 |
| `import subprocess` | 导入启动子程序的工具 |
| `Path(__file__)` | 得到当前脚本自己的位置 |
| `.resolve().parent` | 转为绝对路径，再取所在目录 |
| `/ 'bin' / 'verify_livox_stream'` | 拼出同目录下原生检查器的路径 |
| `subprocess.call([str(observer)])` | 启动检查器并等待完成，不通过 shell 拼接命令 |
| `raise SystemExit(...)` | 把检查器的返回码交给终端 |

此入口需要安装布局为 `~/livox_runtime/verify_livox_stream.py` 和 `~/livox_runtime/bin/verify_livox_stream`。仓库里没有二进制文件，因此不要直接从 `runtime/` 运行它并期待自动编译。

## 5. C++ 检查器如何读

源码：[tools/stream_verifier/verify_livox_stream.cpp](../tools/stream_verifier/verify_livox_stream.cpp)。每个主要语句上方都附了中文注释。

### 5.1 Stream 结构

`Stream` 保存某一种消息的计数、异常数、上一个消息时戳以及首末接收时刻。程序创建 `cloud` 和 `imu` 两个对象，独立统计。

`record(stamp)` 在收到消息时调用；它检查时戳是否为正且严格递增，然后计数。`rate()` 计算：

```text
平均接收频率 = (接收消息数量 - 1) / (最后接收时刻 - 首次接收时刻)
```

接收时刻使用单调时钟，避免系统校时干扰；消息自带的时戳用于检查顺序，两者用途不同。

### 5.2 点云回调

程序订阅 `/livox/lidar`。预热结束后，每帧都检查声明点数与实际数组长度一致、点数和 timebase 非零；遍历每一个点，检查 x/y/z 是否为有限值。

`std::isfinite` 能排除 NaN 和无穷值，但不会判断地图几何是否正确或外参是否准确。

### 5.3 IMU 回调

程序订阅 `/livox/imu`，记录消息时戳，检查三轴角速度和三轴线加速度是否为有限值。它不检验标定误差、积分漂移或时间同步精度。

### 5.4 执行器和时间窗口

`SingleThreadedExecutor` 依次执行就绪回调。开始 5 秒仍持续接收消息，但回调立即返回，不把启动积压计入统计。随后统计 25 秒，总运行时间约 30 秒。

原生 C++ 消息处理避免把每帧约 2 万个点转换成大量 Python 对象，因此能更可靠地测量这条链路。

### 5.5 passed 的含义

通过门槛为：点云至少 100 帧、IMU 至少 2,000 条；异常计数为零；点云平均 8～12 Hz、IMU 平均 150～250 Hz。本次实际测得约 10 / 200 Hz。

这些门槛只用于本次采集诊断，不能据此宣称长期零丢包、建图成功或标定正确。

## 6. CMakeLists 如何使用

[CMakeLists.txt](../tools/stream_verifier/CMakeLists.txt) 已逐行注释。它找到 ROS2 包，编译检查器，并支持将二进制安装到某个前缀的 `bin/`。

如果在一个**工具链完整且可用**的树莓派或 ARM64 Ubuntu 环境中重建：

```bash
# 使用本次独立环境；先确认对应驱动和依赖已经安装。
source ~/livox_runtime/env.sh

# 进入树莓派上的仓库。若实际克隆目录不同，请修改路径。
cd ~/projects/mid360-notes

# CMake 从这两个前缀找到驱动包和干净 ROS 基础包。
cmake -S livox-mid360/tools/stream_verifier -B build/stream-verifier \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_PREFIX_PATH="$HOME/livox_runtime/install/livox_ros_driver2;$HOME/livox_runtime/ros-clean/opt/ros/humble"

# 单线程构建，避免编译内存峰值过高。
cmake --build build/stream-verifier --parallel 1
```

当前树莓派原系统编译器和部分头文件有已有损坏，上面的通用命令不保证能直接重建；本次成功使用的是另备的干净工具链。已安装检查器可直接运行，不需要为读代码而重编译。现场具体构建命令见 `archive/session-scripts/pi_build_stream_verifier.sh`。

## 7. 带注释的版本与运行目录的关系

本仓库补充中文注释的代码用于阅读和长期管理，没有通过本次 Git 整理覆盖树莓派现有运行文件。若以后修改功能，应先在分支中提交、编译验证，再按需部署；不要只因为仓库文件更新就假定运行目录已经更新。
