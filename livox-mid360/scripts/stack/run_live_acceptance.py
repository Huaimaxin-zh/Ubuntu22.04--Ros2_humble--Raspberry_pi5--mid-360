#!/usr/bin/env python3
"""在当前树莓派上分阶段验收真实雷达；仅管理本脚本创建的进程。

依次检查驱动、默认 FAST-LIO 和短时保存模式；结束时尝试停止本轮进程并记录实际退出状态。
原始日志和 PCD 留在树莓派，结构化结果可供后续写入配置记录。
"""
from datetime import datetime
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from zoneinfo import ZoneInfo

HOME = Path('/home/xin')
RUNTIME = HOME / 'livox_runtime'
SETUP = HOME / 'livox_stack_setup'
STAMP = datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d-%H%M%S')
OUT = RUNTIME / 'logs' / ('live-acceptance-' + STAMP)
OUT.mkdir(parents=True, exist_ok=False)
owned = []
result = {'started_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
          'passed': False, 'phases': {}, 'logs': str(OUT),
          'scope': '短时真实数据、算法输出与PCD保存；不代表建图精度或长期稳定性。'}


def say(message):
    """立即输出进度，便于远程观察，不等到整个测试结束才显示。"""
    print(datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(), message, flush=True)


def persist():
    """每阶段落盘，异常退出时也保留已经取得的证据。"""
    (OUT / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')


def command(name, arguments, timeout=25):
    """命令采用参数列表，不拼接外来文本；结果和输出分别记录。"""
    with (OUT / (name + '.log')).open('w') as log:
        completed = subprocess.run(arguments, stdout=log, stderr=subprocess.STDOUT,
                                   timeout=timeout, cwd=RUNTIME)
    if completed.returncode:
        raise RuntimeError(f'{name}退出码{completed.returncode}；见对应日志')


def start(name, script, *arguments):
    """独立进程组用于只停止本次启动的节点，不使用全局pkill。"""
    log = (OUT / (name + '.log')).open('w')
    process = subprocess.Popen(['bash', str(RUNTIME / script), *arguments],
                               stdout=log, stderr=subprocess.STDOUT,
                               cwd=RUNTIME, start_new_session=True)
    item = (name, process, log)
    owned.append(item)
    say(f'{name}启动，PID={process.pid}')
    return item


def stop(item):
    """只向launch发SIGINT，由它转发一次；超时才终止整个进程组。"""
    name, process, log = item
    method = 'already_exited'
    if process.poll() is None:
        method = 'SIGINT'
        try:
            # 同时给launch和子节点发信号会触发两次shutdown，必须避免。
            process.send_signal(signal.SIGINT)
        except ProcessLookupError:
            pass  # 进程恰好在poll与发信号之间退出，继续wait取得真实退出码。
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            method = 'SIGTERM'
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                method = 'SIGKILL'
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
    log.close()
    # launch自己退出0不代表子节点退出0，必须一并核对其子节点退出日志。
    content = (OUT / (name + '.log')).read_text(errors='replace')
    child_clean = 'process has finished cleanly' in content
    child_errors = [line for line in content.splitlines() if 'process has died' in line]
    normal = (process.returncode == 0 and method in ('SIGINT', 'already_exited')
              and child_clean and not child_errors)
    result.setdefault('shutdown', {})[name] = {
        'returncode': process.returncode, 'method': method, 'normal': normal,
        'child_exit_clean': child_clean, 'child_exit_errors': child_errors}
    say(f'{name}已停止，退出码={process.returncode}，方式={method}')
    return normal


def ensure_alive():
    """验收过程中发现自己启动的节点提前退出，即判为失败。"""
    for name, process, log in owned:
        if not log.closed and process.poll() is not None:
            raise RuntimeError(f'{name}提前退出，退出码={process.returncode}')


def measure(name, input_only=False):
    """实收35秒：5秒预热、30秒统计；不只检查话题名称。"""
    ensure_alive()
    destination = OUT / (name + '.json')
    # C++直接读取消息，避免Python逐点对象转换占满CPU、拖慢IMU计数。
    verifier = SETUP / 'native-verifier/build/verify_live_stream_native'
    if not verifier.is_file():
        raise RuntimeError('缺少低开销C++验收器；不回退到已发现负载瓶颈的Python统计')
    arguments = ['bash', '-c',
                 'source /home/xin/livox_runtime/env.sh && exec "$@"',
                 'verify-stream', str(verifier),
                 '--output', str(destination)]
    if input_only:
        arguments.append('--input-only')
    say(f'开始{name}实收检查')
    command(name, arguments, timeout=55)
    ensure_alive()
    data = json.loads(destination.read_text())
    result['phases'][name] = data
    persist()
    if not data['passed']:
        raise RuntimeError(f'{name}数据检查未通过')
    say(name + '通过；' + ', '.join(f"{key}={value['received_hz']:.2f}Hz"
                                      for key, value in data['topics'].items()))


try:
    # 不重复启动用户已经运行的实例，避免端口或话题冲突。
    for path in Path('/proc').glob('[0-9]*/comm'):
        try:
            if path.read_text().strip() in ('fastlio_mapping', 'livox_ros_drive'):
                raise RuntimeError('检测到已有驱动/算法进程，请先核对，未启动新实例')
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            pass
    command('lidar-ping', ['ping', '-c', '3', '-W', '2', '192.168.123.20'])
    if (Path('/sys/class/net/eth0/carrier').read_text().strip() != '1'):
        raise RuntimeError('eth0没有物理链路')
    driver = start('driver', 'run_livox.sh')
    time.sleep(6)
    measure('driver-input', input_only=True)
    mapping = start('fastlio-default', 'run_fastlio.sh')
    measure('fastlio-default-stream')
    if not stop(mapping):
        raise RuntimeError('默认FAST-LIO未正常退出，不继续启动第二个实例')
    # 不覆盖现有地图；把历史同名文件改名保存在原目录。
    pcd = RUNTIME / 'maps/mid360_map.pcd'
    if pcd.exists():
        pcd.rename(pcd.with_name('mid360_map-before-' + STAMP + '.pcd'))
    mapping_save = start('fastlio-save', 'run_fastlio.sh', '--save-map')
    measure('fastlio-save-stream')
    command('map-save-service', ['bash', '-c',
            'source /home/xin/livox_runtime/env.sh && '
            'exec ros2 service call /map_save std_srvs/srv/Trigger "{}"'], timeout=25)
    # 服务回调可能报告成功但并无有效地图，另查payload及抽样XYZ。
    command('pcd-content', ['python3', str(SETUP / 'check_saved_pcd.py'),
            '--pcd', str(pcd), '--output', str(OUT / 'pcd-content.json')])
    result['map'] = json.loads((OUT / 'pcd-content.json').read_text())
    say(f'地图已保存，POINTS={result["map"]["points"]}，BYTES={pcd.stat().st_size}')
    result['passed'] = True
except BaseException as error:
    result['error'] = f'{type(error).__name__}: {error}'
    say(result['error'])
finally:
    # 算法先停、驱动后停；只清理本次创建的三个节点进程组。
    for item in reversed(owned):
        if not item[2].closed:
            try:
                stop(item)
            except BaseException as error:
                result.setdefault('cleanup_errors', []).append(
                    f'{item[0]}: {type(error).__name__}: {error}')
                say(f'{item[0]}清理异常，继续停止其余自有进程：{error}')
    result['passed'] = (result['passed'] and not result.get('cleanup_errors')
                        and all(item['normal'] for item in result.get('shutdown', {}).values()))
    result['finished_at'] = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
    persist()
    say(f'最终结果：passed={result["passed"]}；{OUT}/result.json')
raise SystemExit(0 if result['passed'] else 1)
