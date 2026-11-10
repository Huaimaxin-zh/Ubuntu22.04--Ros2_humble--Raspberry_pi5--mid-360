# 树莓派 5 + MID360：配置记录、代码与远程开发

这份资料记录 Ubuntu 22.04 ARM64、ROS2 Humble 下配置 MID360 的实际过程，保存启动脚本、原生数据检查器、问题分析和 Git 使用方法。

2026-11-09 实测：预热 5 秒后统计 25 秒，点云 **250 帧 / 10.0002 Hz**，IMU **5,001 条 / 199.994 Hz**，内容检查通过。原始结果见 [验证 JSON](evidence/2026-11-09-stream-result.json)。

2026-11-10 更新：原SD卡未修复，完整备份已通过校验；完整根分区副本修复后五阶段复查退出0。恢复候选镜像尚未在新卡启动测试，原卡写入可靠性高度可疑，不能仅凭副本检查通过认定原卡或ROS环境已恢复。见[维修记录](docs/07-sd-card-recovery-report.md)。

2026-11-10 新卡进展：用户重新烧录的新 SD 卡已完成 ROS2 Humble 基础开发环境及 Git 配置，本机通信、C++ 编译运行、rosdep 与 Git 仓库检查通过。见 [新卡配置记录](docs/09-ros2-git-new-card-setup.md) 和 [精选验收 JSON](evidence/2026-11-10-ros2-git-new-card-setup.json)。

**新卡已完成真实三阶段验收：点云 10 Hz、IMU 200 Hz，FAST-LIO 注册点云和里程计 10 Hz；PCD 保存 17802 点，默认算法、保存算法及驱动正常停止。** SDK 退出时 spdlog 符号冲突已通过本地链接补丁修复。见 [实机记录](docs/11-mid360-fastlio-live-acceptance.md) 与 [结果 JSON](evidence/2026-11-10-mid360-fastlio-live-acceptance.json)。使用 [runtime/pi5](runtime/pi5/README.md) 的新卡运行脚本，上一级 runtime 保留作旧卡历史记录。此前仅软件检查阶段的事实保留在 [软件记录](docs/10-livox-fastlio-new-card-setup.md)。

## 先看哪里

远程 RViz 配置与 CPU/GPU 监控脚本也已归档。监控已在树莓派短时实测；RViz 配置已部署并检查字段，虚拟机真实 DDS 接收与渲染仍待现场验证，不能把局域网 ping 通当作显示验收通过。

| 想完成的事 | 文档 |
| --- | --- |
| 从系统检查、接线到最终验收，按顺序回顾全过程 | [本次配置全过程](docs/00-full-process.md) |
| 用 Windows VS Code 连接树莓派 | [Remote-SSH 逐步操作](docs/01-remote-ssh.md) |
| Remote-SSH 一直初始化、下载中断时怎么处理 | [本次连接故障记录](docs/06-remote-ssh-troubleshooting.md) |
| 把代码和 Markdown 放到现有 GitHub 仓库 | [GitHub 和 Git 操作](docs/02-git-and-github.md) |
| 以后持续记录每次配置、报错和解决过程 | [记录方法和工作流程](docs/03-recording-workflow.md) |
| 了解这次究竟出了什么问题、怎么修复 | [完整故障报告](docs/04-troubleshooting-report.md) |
| 读懂启动、环境和检查器代码 | [代码逐条讲解](docs/05-script-explanation.md) |
| 看现场构建命令和补丁的适用范围 | [恢复命令留档](archive/README.md)、[补丁说明](patches/README.md) |
| 了解异常断电后的SD卡故障、备份、修复失败证据和恢复选择 | [SD卡维修记录](docs/07-sd-card-recovery-report.md)、[验收JSON](evidence/2026-11-10-sd-card-recovery.json) |
| 逐条理解本次SD卡维修用过的指令、风险和yes/no选择 | [维修指令说明](docs/08-sd-card-recovery-commands.md) |
| 新卡安装 ROS2 Humble、配置 Git，并理解实际验收结果 | [新卡配置记录](docs/09-ros2-git-new-card-setup.md)、[带注释脚本](scripts/setup/README.md) |
| 新卡安装 SDK2、驱动和 FAST-LIO，理解软件验收与实机验收边界 | [软件配置记录](docs/10-livox-fastlio-new-card-setup.md)、[安装脚本](scripts/stack/README.md)、[新卡运行脚本](runtime/pi5/README.md) |
| 看真实点云、IMU、算法输出、PCD 与退出检查，理解 SDK 修复 | [实机验收记录](docs/11-mid360-fastlio-live-acceptance.md)、[原生检查器](scripts/stack/native-verifier/README.md)、[SDK 补丁](patches/README.md) |
| 在 Ubuntu 虚拟机接收 FAST-LIO 标准点云并用 RViz 显示 | [远程显示步骤](docs/12-vm-rviz-remote-visualization.md)、[RViz 配置](configs/rviz/README.md) |
| 查看树莓派总体和各核 CPU、V3D GPU 引擎、进程、内存与温度 | [监控使用与指标解释](docs/13-pi5-resource-monitor.md)、[带注释脚本](runtime/pi5/monitor_resources.py) |

## 目录用途

```text
runtime/                 启动和环境脚本、检查器 Python 入口
tools/stream_verifier/   原生 C++ 检查器源码和带注释的 CMakeLists
configs/                 雷达配置示例
docs/                    操作教程与故障分析
evidence/                少量可读的实际验证结果
templates/               写新故障记录时使用的模板
user-scripts/            后续加入你自己编写的脚本
patches/                 驱动修改差异和来源说明
archive/session-scripts/ 本次现场恢复命令，仅供复盘
examples/                SSH 配置示例，不含密钥
scripts/setup/           新卡 ROS2 配置与验收脚本、最小 C++ 验证源码
scripts/stack/           新卡 SDK2、驱动与 FAST-LIO 安装和检查脚本
scripts/stack/native-verifier/  新卡低开销 C++ 实收检查器源码
runtime/pi5/             新卡启动脚本和只读资源监控（上级 runtime 为旧卡历史）
configs/pi5/             新卡配置的版本记录与实际部署位置说明
configs/rviz/            虚拟机远程 RViz 配置与使用说明
```

## 旧卡历史启动方式（仅复盘）

以下启动方式对应2026-11-09验证通过的旧卡独立恢复目录，保留以便理解历史测试。新卡请使用上面的 `runtime/pi5` 与软件配置记录；不要从上一级 `runtime/` 覆盖新卡环境。历史命令为：

```bash
# 启动已安装的驱动；保持终端运行，Ctrl+C 停止。
bash ~/livox_runtime/run_livox.sh
```

另开终端检查：

```bash
# 当前终端加载独立环境。
source ~/livox_runtime/env.sh
# 调用原生检查器：5 秒预热、25 秒统计。
python3 ~/livox_runtime/verify_livox_stream.py
```

这个 Git 仓库保存的是代码和记录。**克隆仓库不会自动安装 SDK、ROS 依赖或编译好的驱动。** 历史 `runtime/` 和新卡 `runtime/pi5/` 都曾采用 `/home/xin/livox_runtime` 目录名，但内部依赖布局不同；仓库路径和实际运行目录也不同。

## 本次地址约定

| 角色 | 地址或话题 |
| --- | --- |
| 雷达 | `192.168.123.20` |
| 树莓派雷达有线网口 eth0 | `192.168.123.4/24` |
| Windows 远程连接树莓派 | 使用树莓派 Wi-Fi 地址，本次为 `192.168.0.103`，可能随 DHCP 改变 |
| 点云 / IMU | `/livox/lidar` / `/livox/imu` |
| ROS2 域 | `10` |

历史配置示例见 [MID360_config.example.json](configs/MID360_config.example.json)。新卡请看 [configs/pi5](configs/pi5/README.md)：官方驱动实际读取工作空间源码对应的 JSON，runtime 中的 JSON 是记录副本；FAST-LIO 实际读取 runtime 中的 YAML。修改并推送仓库配置不会自动部署。

## Git 记录与运行的关系

```text
Windows VS Code
    │ Remote-SSH：远程编辑和操作
    ▼
树莓派的 Git 工作目录 ── git push/pull ── GitHub 仓库
    │ 按需要人工部署、编译、验证
    ▼
~/livox_runtime 中已安装的运行环境
```

`git push` 记录源码与文档；它不会自动更新驱动进程、设置网口或重新编译。建议以树莓派上的仓库作为日常开发位置，Windows 的本地副本用于离线查看和资料整理。两端若同时修改，提交后再拉取合并。

## 历史故障与当前验收边界

旧卡原系统的 APT/dpkg、ROS 和 SDK 文件损坏没有整体修复，当时通过独立目录恢复了采集。重新烧录的新卡已完成基础 ROS2、真实雷达采集、短时 FAST-LIO 输出、PCD 内容及正常停止验收；建图精度、重新标定、闭环、跨 Wi-Fi 接收与长期稳定性仍需分别测试。此仓库不包含运行依赖、SD 卡镜像、点云原始数据或 SSH 密钥。

上游源码和版本见 [upstream-versions.json](upstream-versions.json)，来源和许可说明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
