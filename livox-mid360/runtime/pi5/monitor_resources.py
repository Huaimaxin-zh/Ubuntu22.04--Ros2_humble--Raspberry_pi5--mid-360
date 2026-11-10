#!/usr/bin/env python3
"""树莓派5只读资源监控；仅使用Python标准库，无需sudo或额外软件包。"""
import argparse
from datetime import datetime
import os
from pathlib import Path
import sys
import time
from zoneinfo import ZoneInfo


def read_cpu():
    """读取累计CPU时间；只用前8列，避免guest时间被重复计入。"""
    result = {}
    for line in Path('/proc/stat').read_text().splitlines():
        fields = line.split()
        if fields and fields[0].startswith('cpu'):
            ticks = [int(value) for value in fields[1:9]]
            # idle与iowait都属于未执行计算的时间。
            result[fields[0]] = (sum(ticks), ticks[3] + ticks[4])
    return result


def cpu_percent(before, after):
    """两次采样的忙碌时间差÷总时间差；全机总体上限为100%。"""
    total = after[0] - before[0]
    idle = after[1] - before[1]
    return 100.0 * (total - idle) / total if total > 0 else 0.0


def read_gpu():
    """自动寻找V3D gpu_stats；timestamp和runtime单位均为纳秒。"""
    for path in Path('/sys/class/drm').glob('card*/device/gpu_stats'):
        try:
            result = {}
            for line in path.read_text().splitlines()[1:]:
                fields = line.split()
                if len(fields) == 4:
                    # 每行依次是队列名、采样时间、累计任务数、累计忙碌时间。
                    name, timestamp, jobs, runtime = fields
                    result[name] = (int(timestamp), int(runtime), int(jobs))
            if result:
                return result, str(path)
        except (OSError, ValueError):
            continue
    return {}, '没有可读的V3D gpu_stats接口'


def gpu_percent(before, after, name):
    """各引擎可同时工作，分别计算，不能相加当作GPU总体占用。"""
    if name not in before or name not in after:
        return 'N/A'
    elapsed = after[name][0] - before[name][0]
    busy = after[name][1] - before[name][1]
    if elapsed <= 0 or busy < 0:
        return 'N/A'  # 驱动重新加载或计数重置时，不伪造0%。
    return f'{100.0 * busy / elapsed:5.1f}%'


def read_processes():
    """记录进程累计CPU时间；PID+启动时间用于防止PID复用误计。"""
    result = {}
    for path in Path('/proc').glob('[0-9]*/stat'):
        try:
            text = path.read_text()
            opening, closing = text.find('('), text.rfind(')')
            fields = text[closing + 2:].split()
            key = (int(path.parent.name), int(fields[19]))
            result[key] = (text[opening + 1:closing],
                           int(fields[11]) + int(fields[12]), int(fields[21]))
        except (OSError, ValueError, IndexError):
            continue  # 进程在采样过程中结束属于正常情况。
    return result


def memory_and_temperature():
    """内存使用MemAvailable口径；温度从CPU thermal节点读取。"""
    memory = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key, value = line.split(':', 1)
        memory[key] = int(value.split()[0])
    total = memory['MemTotal'] / 1024
    used = (memory['MemTotal'] - memory['MemAvailable']) / 1024
    temperature = 'N/A'
    try:
        temperature = f"{int(Path('/sys/class/thermal/thermal_zone0/temp').read_text()) / 1000:.1f}°C"
    except (OSError, ValueError):
        pass
    return f'内存 {used:.0f}/{total:.0f} MiB  CPU温度 {temperature}'


def positive_interval(text):
    value = float(text)
    if not 0.2 <= value <= 60:
        raise argparse.ArgumentTypeError('采样间隔应为0.2至60秒')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--interval', type=positive_interval, default=1.0, help='刷新间隔秒数，默认1')
    parser.add_argument('--samples', type=int, default=0, help='采样次数，0为持续运行')
    parser.add_argument('--no-clear', action='store_true', help='保留每次输出，适合记录日志')
    args = parser.parse_args()
    if args.samples < 0:
        parser.error('--samples不能为负数')
    ticks_per_second = os.sysconf('SC_CLK_TCK')
    page_mib = os.sysconf('SC_PAGE_SIZE') / 1024 / 1024
    before_cpu = read_cpu()
    before_gpu, _ = read_gpu()
    before_process = read_processes()
    before_time = time.monotonic()
    count = 0
    try:
        while args.samples == 0 or count < args.samples:
            time.sleep(args.interval)
            after_cpu = read_cpu()
            after_gpu, gpu_source = read_gpu()
            after_process = read_processes()
            now = time.monotonic()
            elapsed = now - before_time
            if sys.stdout.isatty() and not args.no_clear:
                print('\033[H\033[J', end='')
            print(f'树莓派资源监控  {datetime.now(ZoneInfo("Asia/Shanghai")):%Y-%m-%d %H:%M:%S} 北京时间  Ctrl+C结束')
            print(f'CPU总体: {cpu_percent(before_cpu["cpu"], after_cpu["cpu"]):5.1f}% （全机满载=100%）')
            cores = [name for name in after_cpu if name != 'cpu' and name in before_cpu]
            print('  '.join(f'{name}: {cpu_percent(before_cpu[name], after_cpu[name]):5.1f}%'
                            for name in cores))
            # cpu/cache_clean是V3D辅助队列，不能当成CPU总体或GPU计算引擎。
            print('GPU引擎: ' + '  '.join(f'{name}={gpu_percent(before_gpu, after_gpu, name)}'
                                          for name in ('bin', 'render', 'tfu', 'csd')))
            print(f'GPU来源: {gpu_source}')
            print(memory_and_temperature())
            print('主要进程：PID    CPU%(单核满载=100%)    内存MiB    名称')
            rows = []
            for key, (name, ticks, pages) in after_process.items():
                if key in before_process:
                    percent = 100.0 * max(0, ticks - before_process[key][1]) / (elapsed * ticks_per_second)
                    rows.append((percent, key[0], max(0, pages) * page_mib, name))
            for percent, pid, memory, name in sorted(rows, reverse=True)[:5]:
                print(f'          {pid:<7} {percent:8.1f}%             {memory:7.1f}    {name}')
            print(flush=True)
            before_cpu, before_gpu = after_cpu, after_gpu
            before_process, before_time = after_process, now
            count += 1
    except KeyboardInterrupt:
        print('\n监控已结束；雷达和FAST-LIO继续运行。')


if __name__ == '__main__':
    main()
