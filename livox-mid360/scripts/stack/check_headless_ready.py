#!/usr/bin/env python3
"""在不启动雷达驱动、不接收实机数据的前提下检查软件是否准备就绪。

先以普通用户加载 ~/livox_runtime/env.sh，再执行本文件。
本工具只执行驱动 launch 的 --show-args；该操作解析启动文件但不启动驱动。
FAST-LIO 会短暂运行在独立 Domain 177、本机通信范围内，随后停止。
它验证软件初始化，不能据此声称雷达采集或实机建图成功。
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time
import traceback


def positive_seconds(value):
    """所有子程序和初始化等待都必须有有限的超时。"""
    import math
    seconds = float(value)
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError('必须是大于 0 的有限秒数')
    return seconds


def signal_own_group(process, signum):
    """只向本工具以 start_new_session 创建的进程组发信号。"""
    try:
        os.killpg(process.pid, signum)
    except ProcessLookupError:
        pass


def stop_owned_process(process):
    """优先正常 SIGINT；超时后依次 TERM/KILL，任何等待都有上限。"""
    if process.poll() is not None:
        return {'method': 'already_exited', 'returncode': process.returncode}
    for signum, wait_seconds, label in (
        (signal.SIGINT, 10, 'SIGINT'),
        (signal.SIGTERM, 4, 'SIGTERM'),
        (signal.SIGKILL, 4, 'SIGKILL'),
    ):
        signal_own_group(process, signum)
        try:
            returncode = process.wait(timeout=wait_seconds)
            return {'method': label, 'returncode': returncode}
        except subprocess.TimeoutExpired:
            continue
    return {'method': 'shutdown_timeout', 'returncode': process.poll()}


def run_bounded(command, environment, timeout, log_file, cwd=None):
    """运行只读工具命令，不经过 shell，不允许无限等待。"""
    with log_file.open('w', encoding='utf-8') as output:
        output.write('$ ' + ' '.join(command) + '\n')
        output.flush()
        process = subprocess.Popen(
            command, env=environment, cwd=cwd, stdout=output,
            stderr=subprocess.STDOUT, start_new_session=True,
        )
        timed_out = False
        stop = None
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
        finally:
            if process.poll() is None:
                stop = stop_owned_process(process)
    return {
        'command': command,
        'returncode': process.returncode,
        'timed_out': timed_out,
        'stop': stop,
        'log': str(log_file),
        'text': log_file.read_text(encoding='utf-8', errors='replace'),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--runtime', type=Path, default=Path('/home/xin/livox_runtime'),
                        help='运行配置目录，默认 /home/xin/livox_runtime')
    parser.add_argument('--output', type=Path, default=Path('/home/xin/livox_runtime/logs/headless-ready.json'),
                        help='保存软件检查 JSON 的路径')
    parser.add_argument('--log-dir', type=Path, help='可选的独立日志目录；默认位于 output 同目录的时间子目录')
    parser.add_argument('--init-timeout', type=positive_seconds, default=30.0,
                        help='FAST-LIO 初始化等待上限，默认 30 秒')
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    logs = args.log_dir or args.output.parent / ('headless-ready-' + stamp)
    logs.mkdir(parents=True, exist_ok=False)
    checks = []
    errors = []
    mapping_process = None
    mapping_log = None
    shutdown = None
    interrupted = False

    # 这份环境只交给本工具启动的子进程，不修改调用者 shell 的环境。
    environment = os.environ.copy()
    environment['ROS_DOMAIN_ID'] = '177'
    environment['ROS_LOCALHOST_ONLY'] = '1'
    environment['RMW_IMPLEMENTATION'] = 'rmw_fastrtps_cpp'
    environment['ROS_LOG_DIR'] = str(logs / 'ros')
    environment['RCUTILS_COLORIZED_OUTPUT'] = '0'
    environment['PYTHONUNBUFFERED'] = '1'
    # 清除发现服务器和外部 DDS profile，避免从用户环境继承远端发现配置。
    for name in ('ROS_DISCOVERY_SERVER', 'ROS_SUPER_CLIENT',
                 'FASTDDS_DEFAULT_PROFILES_FILE', 'FASTRTPS_DEFAULT_PROFILES_FILE'):
        environment.pop(name, None)

    def record(name, passed, **details):
        checks.append({'name': name, 'passed': bool(passed), **details})
        print(f'{"PASS" if passed else "FAIL"}: {name}', file=sys.stderr, flush=True)

    try:
        # 导入消息及其二进制类型支持，确认 source 后 Python 可真正加载接口。
        from ament_index_python.packages import get_package_prefix
        from rclpy.type_support import check_for_type_support
        from livox_ros_driver2.msg import CustomMsg
        from sensor_msgs.msg import Imu, PointCloud2
        for message_type in (CustomMsg, Imu, PointCloud2):
            check_for_type_support(message_type)
            message_type()
        record('python_message_imports', True,
               types=['livox_ros_driver2/msg/CustomMsg', 'sensor_msgs/msg/Imu', 'sensor_msgs/msg/PointCloud2'])

        # 只查找驱动文件与共享库，不以任何参数运行驱动可执行文件。
        executables = {
            'livox_ros_driver2': Path(get_package_prefix('livox_ros_driver2')) / 'lib/livox_ros_driver2/livox_ros_driver2_node',
            'fast_lio': Path(get_package_prefix('fast_lio')) / 'lib/fast_lio/fastlio_mapping',
        }
        for package, executable in executables.items():
            exists = executable.is_file() and os.access(executable, os.X_OK)
            record(package + '_executable', exists, path=str(executable))
            if not exists:
                raise RuntimeError(f'缺少可执行文件：{executable}')
            dependency = run_bounded(['ldd', str(executable)], environment, 15, logs / (package + '-ldd.log'))
            # ldd 不启动节点；returncode 与 not found 必须同时核对。
            linked = not dependency['timed_out'] and dependency['returncode'] == 0 and 'not found' not in dependency['text']
            record(package + '_dynamic_libraries', linked,
                   returncode=dependency['returncode'], timed_out=dependency['timed_out'], log=dependency['log'])
            if not linked:
                raise RuntimeError(f'{package} 共享库检查失败，见 {dependency["log"]}')

        # 驱动可执行文件可能只是组件加载器；SDK/PCL 实际由组件共享库链接。
        # 因此必须单独检查组件库，不能只凭 node 可执行文件的 ldd 判为通过。
        component = Path(get_package_prefix('livox_ros_driver2')) / 'lib/liblivox_ros_driver2.so'
        record('livox_driver_component_library', component.is_file(), path=str(component))
        if not component.is_file():
            raise RuntimeError(f'缺少驱动组件共享库：{component}')
        dependency = run_bounded(
            ['ldd', str(component)], environment, 15, logs / 'livox-driver-component-ldd.log')
        linked = not dependency['timed_out'] and dependency['returncode'] == 0 and 'not found' not in dependency['text']
        record('livox_driver_component_dynamic_libraries', linked,
               returncode=dependency['returncode'], timed_out=dependency['timed_out'],
               sdk_dependency_listed='liblivox_lidar_sdk_shared.so' in dependency['text'],
               log=dependency['log'])
        if not linked:
            raise RuntimeError(f'驱动组件共享库依赖检查失败，见 {dependency["log"]}')

        # --show-args 只解析 LaunchDescription；不会执行其中的 driver Node action。
        driver_parse = run_bounded(
            ['ros2', 'launch', 'livox_ros_driver2', 'msg_MID360_launch.py', '--show-args'],
            environment, 20, logs / 'driver-launch-show-args.log', cwd=str(args.runtime),
        )
        parsed = not driver_parse['timed_out'] and driver_parse['returncode'] == 0
        record('driver_launch_parse_only', parsed, driver_started=False,
               returncode=driver_parse['returncode'], timed_out=driver_parse['timed_out'], log=driver_parse['log'])
        if not parsed:
            raise RuntimeError('驱动启动文件解析失败；未启动驱动')

        # 读取本次的日常参数文件；要求关闭保存，防止软件检查误写地图。
        import yaml
        config_path = args.runtime / 'config/mid360_pi5.yaml'
        config = yaml.safe_load(config_path.read_text(encoding='utf-8'))
        parameters = config['/**']['ros__parameters']
        safe_config = parameters['pcd_save']['pcd_save_en'] is False
        record('mapping_default_config', safe_config, path=str(config_path),
               pcd_save_en=parameters['pcd_save']['pcd_save_en'],
               map_en=parameters['publish']['map_en'])
        if not safe_config:
            raise RuntimeError('默认配置开启了地图保存，已停止软件检查')

        command = [
            'ros2', 'launch', 'fast_lio', 'mapping.launch.py',
            'config_path:=' + str(config_path.parent),
            'config_file:=mid360_pi5.yaml', 'rviz:=false', 'use_sim_time:=false',
        ]
        mapping_path = logs / 'fastlio-no-input.log'
        mapping_log = mapping_path.open('w', encoding='utf-8')
        mapping_log.write('$ ' + ' '.join(command) + '\n')
        mapping_log.flush()
        # 此进程组只包含本次 FAST-LIO 启动器及其子进程；绝不启动驱动。
        mapping_process = subprocess.Popen(
            command, env=environment, cwd=str(args.runtime), stdout=mapping_log,
            stderr=subprocess.STDOUT, start_new_session=True,
        )
        deadline = time.monotonic() + args.init_timeout
        initialized_at = None
        while time.monotonic() < deadline:
            if mapping_process.poll() is not None:
                break
            text = mapping_path.read_text(encoding='utf-8', errors='replace')
            if 'Node init finished.' in text and initialized_at is None:
                initialized_at = time.monotonic()
            # 初始化日志出现后再观察两秒存活，避免把立即崩溃判为通过。
            if initialized_at is not None and time.monotonic() - initialized_at >= 2:
                break
            time.sleep(0.2)
        initialized = (initialized_at is not None and mapping_process.poll() is None
                       and time.monotonic() - initialized_at >= 2)
        record('fastlio_no_input_initialization', initialized, log=str(mapping_path),
               ros_domain_id=177, ros_localhost_only=True, rviz=False,
               hardware_data_tested=False, alive_when_checked=mapping_process.poll() is None)
        if not initialized:
            raise RuntimeError('FAST-LIO 无输入初始化失败或超时')

        # 用单独的只读检查节点查看软件服务图；不调用 /map_save。
        inspect_code = '''import json,time,rclpy
from rclpy.node import Node
rclpy.init()
node=Node('headless_ready_service_inspector')
services={}
deadline=time.monotonic()+8
try:
    while time.monotonic()<deadline:
        rclpy.spin_once(node,timeout_sec=0.2)
        services=dict(node.get_service_names_and_types())
        if 'std_srvs/srv/Trigger' in services.get('/map_save',[]):
            break
    found='std_srvs/srv/Trigger' in services.get('/map_save',[])
    print(json.dumps({'map_save_advertised':found,'map_save_called':False}))
finally:
    node.destroy_node()
    rclpy.shutdown()
raise SystemExit(0 if found else 1)
'''
        graph = run_bounded([sys.executable, '-c', inspect_code], environment, 12, logs / 'software-service-graph.log')
        graph_ok = not graph['timed_out'] and graph['returncode'] == 0
        record('map_save_service_advertised_only', graph_ok, service_called=False,
               returncode=graph['returncode'], timed_out=graph['timed_out'], log=graph['log'])
        record('fastlio_alive_after_graph_check', mapping_process.poll() is None)
    except KeyboardInterrupt:
        interrupted = True
        errors.append('用户中断；本次检查未完成')
    except Exception as exception:
        errors.append(f'{exception.__class__.__name__}: {exception}')
        traceback.print_exc(file=sys.stderr)
    finally:
        if mapping_process is not None:
            shutdown = stop_owned_process(mapping_process)
            # 需要升级到 TERM/KILL 时如实记录，不把被强制停止当成正常退出。
            normal = shutdown['method'] == 'SIGINT' and shutdown['returncode'] in (0, -signal.SIGINT, 130)
            record('fastlio_owned_process_shutdown', normal, **shutdown)
        if mapping_log is not None:
            mapping_log.close()

    result = {
        'schema_version': 1,
        'finished_utc': datetime.now(timezone.utc).isoformat(),
        'hostname': platform.node(),
        'passed': bool(checks) and all(check['passed'] for check in checks) and not errors and not interrupted,
        'scope': '软件依赖、驱动启动文件解析、FAST-LIO 无输入初始化和正常退出；不代表实机采集或建图通过。',
        'driver_started': False,
        'lidar_communication_started': False,
        'hardware_data_tested': False,
        'map_save_called': False,
        'interrupted': interrupted,
        'checks': checks,
        'errors': errors,
        'logs': str(logs),
    }
    text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + '\n', encoding='utf-8')
    except OSError:
        traceback.print_exc(file=sys.stderr)
        print(text)
        return 1
    print(text)
    return 0 if result['passed'] else (130 if interrupted else 1)


if __name__ == '__main__':
    raise SystemExit(main())
