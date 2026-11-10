# 新卡 MID360 / FAST-LIO 配置记录

这里保存本次已经生成并用于软件检查的三份配置；不是自动部署目录。提交或推送仓库不会自动修改运行中的驱动或算法参数。

| 仓库文件 | 实际使用位置 |
| --- | --- |
| `MID360_config.json` | 官方驱动实际读 `~/ws_livox/src/livox_ros_driver2/config/MID360_config.json`，通过 symlink-install 对应安装目录 |
| `mid360_pi5.yaml` | 默认 FAST-LIO 脚本实际读 `~/livox_runtime/config/mid360_pi5.yaml` |
| `mid360_pi5_save.yaml` | `--save-map` 模式实际读 `~/livox_runtime/config/mid360_pi5_save.yaml` |

`~/livox_runtime/config/MID360_config.json` 是生成工具额外保存的同内容记录副本；官方 `msg_MID360_launch.py` 没有切换为读取它。**只修改这份 runtime JSON 副本，不会改变实际驱动配置。**

MID360 地址为 `192.168.123.20`，主机接收地址为树莓派 eth0 的 `192.168.123.4/24`。JSON 只配置驱动所用地址，不改变雷达固件或设备现有 IP；持久网口文件为 `/etc/systemd/network/05-livox-eth0.network`，只匹配 eth0。

默认 YAML 关闭 `map_en`、`path_en`、`pcd_save_en`；短时保存 YAML 开启对应缓存用于后续保存检查。两者均关闭在线外参估计，使用上游 MID360 内置 IMU 外参，不代表实测重新标定。地图文件目标为 `/home/xin/livox_runtime/maps/mid360_map.pcd`。

修改仓库配置后，应先备份实际配置、检查差异，再把所需文件同步到上表位置。驱动 JSON 和 FAST-LIO YAML 修改保存后，需要相应进程重新启动才会重新读取；本轮没有启动驱动。

首次生成脚本 [configure_stack.py](../../scripts/stack/configure_stack.py) 从上游原件生成这些文件。重复运行可能覆盖以后手动调整的参数，不能把它当作无损同步工具。完整配置说明和未来地图验收步骤见 [新卡软件记录](../../docs/10-livox-fastlio-new-card-setup.md)。

配置来源：Livox 驱动 JSON 基于官方 Livox 项目，FAST-LIO YAML 基于 Ericsii/FAST_LIO_ROS2 的 `mid360.yaml`。上游许可和版权继续适用，见 [来源说明](../../THIRD_PARTY_NOTICES.md)。
