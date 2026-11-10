#!/usr/bin/env python3
"""生成本卡的雷达/FAST-LIO配置，备份上游原件；不改变雷达固件或IP。"""
from pathlib import Path
import copy
import json
import shutil
import yaml

# 本次确认的实际接线：MID360 -> eth0；wlan0 用于 SSH 和上网。
home = Path('/home/xin')
# 阻止在Windows、本机其他账号或sudo/root环境下误运行这份专用脚本。
if Path.home() != home:
    raise SystemExit('请在树莓派xin用户的终端运行，不能在Windows或sudo环境执行。')
setup = home / 'livox_stack_setup'
runtime = home / 'livox_runtime'
driver = home / 'ws_livox/src/livox_ros_driver2'
fastlio = home / 'ws_fastlio/src/FAST_LIO_ROS2'
for directory in (runtime / 'config', runtime / 'maps', runtime / 'logs', setup / 'upstream-configs'):
    directory.mkdir(parents=True, exist_ok=True)

# 官方驱动通过 package_ROS2.xml 选择 ROS2；不用会清空工作空间的 build.sh。
shutil.copy2(driver / 'package_ROS2.xml', driver / 'package.xml')
json_file = driver / 'config/MID360_config.json'
original = setup / 'upstream-configs/MID360_config.json'
# 原始备份只创建一次；重复执行不会把已改配置误当原件。
if not original.exists():
    shutil.copy2(json_file, original)
config = json.loads(original.read_text())
host = config['MID360']['host_net_info']
for name in ('cmd_data_ip', 'push_msg_ip', 'point_data_ip', 'imu_data_ip'):
    host[name] = '192.168.123.4'
config['lidar_configs'][0]['ip'] = '192.168.123.20'
config['lidar_configs'][0]['pcl_data_type'] = 1
config['lidar_configs'][0]['pattern_mode'] = 0
formatted = json.dumps(config, indent=2) + '\n'
# 官方 msg_MID360_launch.py 读取驱动安装目录中的这份配置。
# --symlink-install 让它对应源码的配置文件。
json_file.write_text(formatted)
# 另存一份在 runtime 中，便于学习查看和版本记录。
(runtime / 'config/MID360_config.json').write_text(formatted)

# 基于上游 MID360 YAML，只修改本卡运行时相关选项。
original_yaml = fastlio / 'config/mid360.yaml'
shutil.copy2(original_yaml, setup / 'upstream-configs/mid360.yaml')
base = yaml.safe_load(original_yaml.read_text())
parameters = base['/**']['ros__parameters']
# 使用MID360内置IMU的上游给定外参，不声称进行了重新标定。
parameters['mapping']['extrinsic_est_en'] = False
parameters['runtime_pos_log_enable'] = False
# 日常默认输出单帧注册点云和里程计，不累加完整地图/轨迹到无界缓存。
parameters['publish']['map_en'] = False
parameters['publish']['path_en'] = False
parameters['pcd_save']['pcd_save_en'] = False
parameters['map_file_path'] = str(runtime / 'maps/mid360_map.pcd')
header = (
    '# 树莓派5 + MID360；基于 Ericsii/FAST_LIO_ROS2 上游 mid360.yaml。\n'
    '# /livox/lidar 使用 CustomMsg，/livox/imu 使用 sensor_msgs/Imu。\n'
    '# 默认关闭整图缓存和PCD累积，保留注册点云与里程计。\n'
)
(runtime / 'config/mid360_pi5.yaml').write_text(header + yaml.safe_dump(base, sort_keys=False))

# 独立的短时保存配置：只有 map_en 与 pcd_save_en 同时开启才有实际缓存。
save_config = copy.deepcopy(base)
save_parameters = save_config['/**']['ros__parameters']
save_parameters['publish']['map_en'] = True
save_parameters['publish']['path_en'] = True
save_parameters['pcd_save']['pcd_save_en'] = True
(runtime / 'config/mid360_pi5_save.yaml').write_text(
    '# 仅供短时建图/保存验收；建议每次60-120秒后停止。\n'
    '# 上游整图缓存会持续增长，不适合长时间常驻。\n'
    + yaml.safe_dump(save_config, sort_keys=False)
)
# 上游会在源码ROOT_DIR下创建日志，保留这些可写目录以避免空FILE指针。
(fastlio / 'Log').mkdir(exist_ok=True)
(fastlio / 'PCD').mkdir(exist_ok=True)
print('MID360_CONFIG_HOST=192.168.123.4 LIDAR=192.168.123.20')
print('FASTLIO_CONFIGS_CREATED')
