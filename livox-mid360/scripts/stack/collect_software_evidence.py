#!/usr/bin/env python3
"""收集本轮软件准备结果；不启动雷达，不上传原始日志或认证信息。"""
from datetime import datetime
import json
from pathlib import Path
import subprocess
from zoneinfo import ZoneInfo
import yaml

home = Path('/home/xin')
setup = home / 'livox_stack_setup'
runtime = home / 'livox_runtime'


def command(*arguments):
    """使用参数列表执行只读命令，设置超时，不经shell拼接。"""
    return subprocess.check_output(arguments, text=True, timeout=20).strip()


def status(name):
    """原样保留状态，包括首次检查命名错误导致的非零状态。"""
    return (setup / name).read_text().strip()


config = json.loads((runtime / 'config/MID360_config.json').read_text())
default = yaml.safe_load((runtime / 'config/mid360_pi5.yaml').read_text())['/**']['ros__parameters']
save = yaml.safe_load((runtime / 'config/mid360_pi5_save.yaml').read_text())['/**']['ros__parameters']
headless = json.loads((runtime / 'logs/headless-ready.json').read_text())
result = {
    'recorded_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
    'scope': '新卡软件安装、编译和隔离环境启动检查；用户要求雷达以后再启动。',
    'hardware_data_tested': False,
    'driver_started': False,
    'mapping_with_real_data_tested': False,
    'map_save_with_real_data_tested': False,
    'platform': {
        'architecture': command('uname', '-m'),
        'kernel': command('uname', '-r'),
        'ros_distro': 'humble',
        'user': command('whoami'),
    },
    'upstream': {
        'sdk2': {
            'url': 'https://github.com/Livox-SDK/Livox-SDK2',
            'commit': command('git', '-C', str(home / 'src/Livox-SDK2'), 'rev-parse', 'HEAD'),
            'install_prefix': str(home / 'livox_sdk2'),
        },
        'driver': {
            'url': 'https://github.com/Livox-SDK/livox_ros_driver2',
            'commit': command('git', '-C', str(home / 'ws_livox/src/livox_ros_driver2'), 'rev-parse', 'HEAD'),
        },
        'fast_lio': {
            'url': 'https://github.com/Ericsii/FAST_LIO_ROS2',
            'commit': command('git', '-C', str(home / 'ws_fastlio/src/FAST_LIO_ROS2'), 'rev-parse', 'HEAD'),
            'ikd_tree_commit': command('git', '-C', str(home / 'ws_fastlio/src/FAST_LIO_ROS2/include/ikd-Tree'), 'rev-parse', 'HEAD'),
            'release_cxx_flags': '-O1 -DNDEBUG --param=ggc-min-expand=10 --param=ggc-min-heapsize=32768',
            'build_parallelism': 1,
        },
    },
    'states': {
        'sdk2': status('sdk2.status'),
        'original_dependency_script': status('dependencies.status'),
        'dependency_recheck': status('dependencies-verified.status'),
        'ros_stack_build': status('ros-stack.status'),
        'dpkg_audit_empty': not command('dpkg', '--audit'),
    },
    'dependency_versions': command(
        'dpkg-query', '-W', 'libpcl-dev', 'libapr1-dev', 'libeigen3-dev',
        'ros-humble-pcl-conversions', 'ros-humble-pcl-ros').splitlines(),
    'network': {
        'host_ethernet_ip': config['MID360']['host_net_info']['point_data_ip'],
        'lidar_ip': config['lidar_configs'][0]['ip'],
        'persistent_config': '/etc/systemd/network/05-livox-eth0.network',
    },
    'runtime': {
        'directory': str(runtime),
        'ros_domain_id': 10,
        'default_map_en': default['publish']['map_en'],
        'default_path_en': default['publish']['path_en'],
        'default_pcd_save_en': default['pcd_save']['pcd_save_en'],
        'save_mode_map_en': save['publish']['map_en'],
        'save_mode_pcd_save_en': save['pcd_save']['pcd_save_en'],
        'extrinsic_estimation_enabled': default['mapping']['extrinsic_est_en'],
        'extrinsic_T_from_upstream': default['mapping']['extrinsic_T'],
        'viewer_installed_by_this_task': False,
    },
    'resolved_issues': [
        '依赖安装本身完成；首次验收使用pcl_common但Jammy实际提供pcl_common-1.12。已修正脚本并普通用户复核通过，原日志保留。',
        'FAST-LIO首次-O2构建laserMapping.cpp时cc1plus被Killed；结合内存观测按内存不足处理，改用-O1和GCC回收参数。',
    ],
    'headless_software_check': headless,
}
output = setup / 'software-result.json'
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False, indent=2))
