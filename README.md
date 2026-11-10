# Ubuntu22.04--ros2_humble--Raspberry_pi5--mid-360
基于Ubuntu22.04操作系统，使用ros2_humble开发库在树莓派5上跑mid-360的数据采集

## 配置过程、代码和远程开发

完整资料见 [livox-mid360](livox-mid360/README.md)，包括带中文注释的启动脚本、原生点云/IMU检查器、故障排查报告，以及 VS Code Remote-SSH 和 GitHub 使用教程。

**新卡当前使用 [runtime/pi5](livox-mid360/runtime/pi5/README.md) 的运行脚本，真实采集与 FAST-LIO 已验收通过。** 点云 10 Hz、IMU 200 Hz，注册点云与里程计 10 Hz；PCD 保存 17802 点，三个节点正常停止。SDK 退出段错误的定位、符号绑定补丁与实测见 [实机验收记录](livox-mid360/docs/11-mid360-fastlio-live-acceptance.md)。[软件配置记录](livox-mid360/docs/10-livox-fastlio-new-card-setup.md) 保留此前 PCL 检查名称及编译内存问题的过程。

- [Windows VS Code 连接树莓派](livox-mid360/docs/01-remote-ssh.md)
- [用 Git 管理脚本和 Markdown](livox-mid360/docs/02-git-and-github.md)
- [本次雷达配置故障报告](livox-mid360/docs/04-troubleshooting-report.md)
- [脚本和检查器逐条讲解](livox-mid360/docs/05-script-explanation.md)
- [2026-11-10 SD卡维修记录与实际结果](livox-mid360/docs/07-sd-card-recovery-report.md)
- [SD卡维修指令、风险和交互说明](livox-mid360/docs/08-sd-card-recovery-commands.md)
- [2026-11-10 新卡 ROS2 Humble / Git 配置与实测](livox-mid360/docs/09-ros2-git-new-card-setup.md)
- [新卡 Livox-SDK2、驱动与 FAST-LIO 安装及软件验收](livox-mid360/docs/10-livox-fastlio-new-card-setup.md)
- [新卡真实采集、FAST-LIO、PCD 与正常停止验收](livox-mid360/docs/11-mid360-fastlio-live-acceptance.md)

2026-11-09 已用真实 MID360 在树莓派上验证：点云约 10 Hz、IMU 约 200 Hz，检查结果见 [实际测试 JSON](livox-mid360/evidence/2026-11-09-stream-result.json)。

2026-11-10 后续状态：原SD卡文件系统修复失败，已完成整卡备份；完整根分区副本修复及只读复查通过，并生成恢复候选镜像。原卡已安全弹出，候选镜像尚需健康新卡进行启动和应用测试。此前雷达测试结果属于历史验证，不代表当前原卡可正常启动。

仓库保存源码和操作记录。运行依赖与编译产物单独管理；克隆仓库不会自动安装完整雷达运行环境。

2026-11-10 新卡进展：重新烧录的新卡已安装 ROS2 Humble 基础开发环境，C++ → Python 本机通信、colcon C++ 构建与运行、rosdep 及 Git 检查通过。该结果对应新卡，不改变旧卡维修结论。见 [配置记录](livox-mid360/docs/09-ros2-git-new-card-setup.md) 和 [精选验收 JSON](livox-mid360/evidence/2026-11-10-ros2-git-new-card-setup.json)。
