# 上游项目与来源

- Livox ROS Driver2：<https://github.com/Livox-SDK/livox_ros_driver2>。
- Livox SDK2：<https://github.com/Livox-SDK/Livox-SDK2>。
- FAST-LIO ROS2：<https://github.com/Ericsii/FAST_LIO_ROS2>；新卡 YAML 基于提交 `2fffc570a25d0df172720bac034fbdb6a13d2162` 的 `config/mid360.yaml` 调整，原项目许可与版权继续适用。该提交仓库随附的许可原文留在 [configs/pi5/LICENSE-FAST-LIO.txt](configs/pi5/LICENSE-FAST-LIO.txt)。
- ROS2 Humble：<https://docs.ros.org/en/humble/>。
- Microsoft VS Code Remote-SSH：<https://code.visualstudio.com/docs/remote/ssh>。
- GitHub SSH 认证：<https://docs.github.com/en/authentication/connecting-to-github-with-ssh>。

本仓库的雷达配置示例和驱动源码差异来自此次对 Livox 工程的配置与修改，原项目许可证和版权声明继续适用。相关驱动源文件中的 Livox MIT 声明已保留在 [patches/LICENSE-MIT-Livox.txt](patches/LICENSE-MIT-Livox.txt)；可在对应上游版本查看完整内容。

新卡 SDK 在官方锁定提交上应用了 [Linux 符号绑定补丁](patches/sdk-spdlog-symbol-binding.patch)，作用和哈希见 [补丁说明](patches/README.md)。SDK 应记录为官方基础提交加本地补丁；驱动源码恢复为官方基础提交，只保留本卡配置改变。

[远程 RViz 配置](configs/rviz/remote_pi5.rviz) 派生自 FAST-LIO ROS2 提交 `2fffc570a25d0df172720bac034fbdb6a13d2162` 的 `rviz/fastlio.rviz`，调整了显示话题、QoS、点云样式与视角。原项目 GPLv2 许可和版权继续适用，许可原文见 [LICENSE-FAST-LIO.txt](configs/pi5/LICENSE-FAST-LIO.txt)。[资源监控说明](docs/13-pi5-resource-monitor.md) 引用树莓派 Linux 内核 V3D 源码解释 `gpu_stats` 计数口径；监控脚本不包含该内核源码。

本仓库不包含第三方安装库、完整官方源码镜像、已下载的软件包或原始雷达数据。新增脚本和说明暂未替仓库所有者指定新的开源许可证；现有仓库若有 LICENSE，应先核对其适用范围。
