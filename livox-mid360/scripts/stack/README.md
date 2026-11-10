# 新卡 MID360 / FAST-LIO 软件配置脚本

本目录保存 2026-11-10 在树莓派5新卡上实际使用的中文注释脚本。完整过程、两次故障与最终软件验收见 [配置记录](../../docs/10-livox-fastlio-new-card-setup.md)，结果见 [JSON](../../evidence/2026-11-10-livox-fastlio-software-ready.json)。

当前树莓派的软件已经安装并通过 13 项软件检查，不需要重跑安装。本轮没有启动雷达驱动，真实点云、IMU 和建图性能待用户通知后验收。

## 目录和安装次序

这些脚本采用本次用户名 `xin` 和确定的工作空间路径，不是可在任意电脑或任意账号直接运行的通用安装器。

| 次序 | 脚本 | 身份和作用 |
| --- | --- | --- |
| 1 | `install_dependencies.sh` | sudo；检查系统，配置 eth0，模拟并安装 PCL/Eigen/APR 与 ROS 转换依赖 |
| 2 | `build_sdk2.sh` | xin；核对锁定提交，编译并安装 SDK2 到 `~/livox_sdk2` |
| 3 | `verify_dependencies.sh` | xin；检查实际包状态、带版本号的 PCL 模块和 CMake 配置 |
| 4 | `configure_stack.py` | xin；首次从上游原件生成本卡 JSON/YAML，选择 ROS2 package.xml |
| 5 | `build_ros_stack.sh` | xin；先驱动再 FAST-LIO，单线程编译，最终采用 `-O1` 和 GCC 内存回收参数 |
| 6 | `check_headless_ready.py` | xin；不启动驱动，短暂启动隔离的无输入 FAST-LIO，检查初始化并正常停止 |
| 7 | `collect_software_evidence.py` | xin；收集版本、状态和已经生成的软件检查结果 |
| 后续 | `verify_live_stream.py` | xin；用户通知接好雷达后，实际订阅输入和建图输出进行验收；本轮未运行 |

依赖安装和 SDK 编译可以分别准备，但 ROS 构建必须在二者完成后运行。FAST-LIO 需要先加载驱动的 CustomMsg 接口。

## 复现前先准备源码

完整上游软件不放入本仓库，需要按配置记录的提交准备以下源码，并初始化 FAST-LIO 的 ikd-Tree 子模块：

- `~/src/Livox-SDK2`
- `~/ws_livox/src/livox_ros_driver2`
- `~/ws_fastlio/src/FAST_LIO_ROS2`

基础 ROS2 环境先按 [新卡 ROS2 / Git 记录](../../docs/09-ros2-git-new-card-setup.md) 准备。不要在已有自定义文件上盲目重新克隆或重新生成配置。

如确需把仓库留档部署到同类新系统，可在阅读脚本后复制到约定目录：

```bash
# 在树莓派 xin 终端创建约定目录；不使用 Windows PowerShell。
mkdir -p ~/livox_stack_setup

# 本目录中的文件是安装和检查脚本；复制并不自动安装或启动软件。
cp ~/projects/raspberrypi-mid360/livox-mid360/scripts/stack/*.sh ~/livox_stack_setup/
cp ~/projects/raspberrypi-mid360/livox-mid360/scripts/stack/*.py ~/livox_stack_setup/
```

按照上表次序执行对应脚本；管理员密码只在树莓派终端输入，不写入脚本。运行环境的三个脚本另见 [runtime/pi5](../../runtime/pi5/README.md)，配置记录与真实部署位置见 [configs/pi5](../../configs/pi5/README.md)。

`configure_stack.py` 会从上游原始配置重新生成文件；它不是保留所有既有自定义参数的同步工具。重新运行前应备份当前参数并检查差异。

## 查看已经完成的软件检查

```bash
# 查看最终 SDK 与 ROS 构建退出码。
cat ~/livox_stack_setup/sdk2.status
cat ~/livox_stack_setup/ros-stack.status

# 独立依赖复核成功；不会重复安装依赖。
cat ~/livox_stack_setup/dependencies-verified.status

# 读取最终软件结果，不启动节点。
cat ~/livox_stack_setup/software-result.json
```

首次依赖脚本留下的 `dependencies.status` 为 `EXIT=1`，原因是安装后检查误用了 `pcl_common`，本卡实际模块名为 `pcl_common-1.12`。该原始状态和日志保留，之后独立复核 `EXIT=0`，不能把首次检查误差当成 PCL 不支持或需要重装。

完整编译日志保存在树莓派 `~/livox_stack_setup`，本仓库只保存少量结构化结果，不包含 `.deb`、源码副本、构建产物、地图或私密认证信息。
