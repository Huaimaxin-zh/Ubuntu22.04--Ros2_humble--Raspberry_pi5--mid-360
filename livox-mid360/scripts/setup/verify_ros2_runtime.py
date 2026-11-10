#!/usr/bin/env python3
"""运行官方 C++ 发布者与 Python 订阅者，确认 ROS2 实际通信。"""

# os 用于建立仅本次测试有效的环境，不改变用户终端设置。
import os
# pathlib 用于将测试日志保存到用户可查看的目录。
from pathlib import Path
# signal 用于正常关闭测试节点，避免遗留后台进程。
import signal
# subprocess 用于启动 ROS 官方提供的两个演示节点。
import subprocess
# time.monotonic 提供不受系统校时影响的超时计时。
import time

# 由调用者先加载 /opt/ros/humble/setup.bash，再执行本文件。
root = Path('/home/xin/pi_setup/verification')
root.mkdir(parents=True, exist_ok=True)
environment = os.environ.copy()
# 使用单独 Domain，并限定本机通信，避免影响局域网中的其他 ROS 节点。
environment['ROS_DOMAIN_ID'] = '177'
environment['ROS_LOCALHOST_ONLY'] = '1'
# 测试使用 Humble 默认的 Fast DDS 后端。
environment['RMW_IMPLEMENTATION'] = 'rmw_fastrtps_cpp'
# 清除继承的发现服务器变量，让此次本机测试独立进行。
environment.pop('ROS_DISCOVERY_SERVER', None)
environment['PYTHONUNBUFFERED'] = '1'

# 日志文件分别记录发布与接收情况。
talker_path = root / 'cpp-talker.log'
listener_path = root / 'python-listener.log'
processes = []
passed = False
try:
    with talker_path.open('w') as talker_log, listener_path.open('w') as listener_log:
        # start_new_session 使每个节点有独立进程组，结束时可一并关闭包装进程。
        listener = subprocess.Popen(
            ['ros2', 'run', 'demo_nodes_py', 'listener'],
            env=environment, stdout=listener_log, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        processes.append(listener)
        talker = subprocess.Popen(
            ['ros2', 'run', 'demo_nodes_cpp', 'talker'],
            env=environment, stdout=talker_log, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        processes.append(talker)
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            # 不仅检查进程启动，还必须实际收到至少五条消息。
            received = listener_path.read_text(errors='replace').count('I heard:')
            if received >= 5:
                passed = True
                break
            if listener.poll() is not None or talker.poll() is not None:
                break
            time.sleep(0.5)
finally:
    # 只停止本脚本自己启动的两个进程组。
    for process in processes:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGINT)
    for process in processes:
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=5)

# 输出可供人工核对的接收记录，并返回真实的测试结果。
print(listener_path.read_text(errors='replace'))
print(f'ROS2_RUNTIME_PASS={passed}')
raise SystemExit(0 if passed else 1)
