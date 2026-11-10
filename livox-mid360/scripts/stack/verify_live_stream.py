#!/usr/bin/env python3
"""实收 ROS2 话题以验收 MID360/FAST-LIO；只订阅，不启动节点或保存地图。

执行前加载 ROS2 和已编译工作空间，例如：
    source ~/livox_runtime/env.sh
    python3 verify_live_stream.py --output ~/livox_runtime/live-result.json

默认先预热 5 秒，再统计 30 秒。仅检查驱动时加 --input-only。
"""

# 以下均为 Python 标准库；ROS2 的导入放在 main 内，便于记录环境缺失错误。
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform
import sys
import time
import traceback


def positive_seconds(value):
    """拒绝零、负数和非有限的测试时长。"""
    seconds = float(value)
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError('必须是大于 0 的有限秒数')
    return seconds


def nonnegative_seconds(value):
    """预热可以为零，但不能为负数或无穷。"""
    seconds = float(value)
    if not math.isfinite(seconds) or seconds < 0:
        raise argparse.ArgumentTypeError('必须是大于等于 0 的有限秒数')
    return seconds


class StreamStats:
    """每个话题独立记录测量窗口内的实收样本和异常计数。"""

    def __init__(self, name, minimum_hz):
        self.name = name
        self.minimum_hz = minimum_hz
        self.count = 0
        self.first_arrival = None
        self.last_arrival = None
        self.first_stamp_ns = None
        self.last_stamp_ns = None
        self.previous_stamp_ns = None
        self.invalid_stamps = 0
        self.equal_stamps = 0
        self.backward_stamps = 0
        self.invalid_payloads = 0
        self.payload_errors = {}
        self.minimum_points = None
        self.maximum_points = None
        self.minimum_line = None
        self.maximum_line = None
        self.minimum_quaternion_norm = None
        self.maximum_quaternion_norm = None

    def receive(self, message, arrival):
        """用单调时钟记录接收，用整数纳秒核对消息时间戳。"""
        self.count += 1
        if self.first_arrival is None:
            self.first_arrival = arrival
        self.last_arrival = arrival
        stamp = message.header.stamp
        seconds, nanoseconds = int(stamp.sec), int(stamp.nanosec)
        stamp_ns = seconds * 1_000_000_000 + nanoseconds
        if seconds < 0 or not 0 <= nanoseconds < 1_000_000_000 or stamp_ns <= 0:
            self.invalid_stamps += 1
            return
        if self.first_stamp_ns is None:
            self.first_stamp_ns = stamp_ns
        if self.previous_stamp_ns is not None:
            if stamp_ns == self.previous_stamp_ns:
                self.equal_stamps += 1
            elif stamp_ns < self.previous_stamp_ns:
                self.backward_stamps += 1
        self.previous_stamp_ns = stamp_ns
        self.last_stamp_ns = stamp_ns

    def invalid(self, *reasons):
        """一个消息可有多种问题，但 invalid_payloads 每个消息只加一次。"""
        if not reasons:
            return
        self.invalid_payloads += 1
        for reason in set(reasons):
            self.payload_errors[reason] = self.payload_errors.get(reason, 0) + 1

    def points(self, count):
        """记录点数范围，帮助识别只有空消息而没有数据的情况。"""
        self.minimum_points = count if self.minimum_points is None else min(self.minimum_points, count)
        self.maximum_points = count if self.maximum_points is None else max(self.maximum_points, count)

    def result(self, elapsed):
        """接收频率用完整测量窗口计算，启动后迟迟没数据也会被计入。"""
        received_hz = self.count / elapsed if elapsed > 0 else 0.0
        reasons = []
        if self.count < 2:
            reasons.append('实收样本少于 2，不能验证持续数据流')
        if received_hz < self.minimum_hz:
            reasons.append(f'实收频率 {received_hz:.3f} Hz 低于阈值 {self.minimum_hz:g} Hz')
        if self.invalid_stamps or self.equal_stamps or self.backward_stamps:
            reasons.append('消息时间戳存在无效、重复或倒退')
        if self.invalid_payloads:
            reasons.append('消息内容检查失败')
        # header_rate 只用于诊断，不拿传感器自报时间替代实际接收频率。
        header_hz = None
        if self.count >= 2 and self.first_stamp_ns is not None and self.last_stamp_ns is not None:
            header_span = self.last_stamp_ns - self.first_stamp_ns
            if header_span > 0:
                header_hz = (self.count - 1) * 1_000_000_000 / header_span
        arrival_hz = None
        if self.count >= 2 and self.last_arrival > self.first_arrival:
            arrival_hz = (self.count - 1) / (self.last_arrival - self.first_arrival)
        return {
            'topic': self.name,
            'passed': not reasons,
            'failures': reasons,
            'received_samples': self.count,
            'received_hz': received_hz,
            'arrival_span_hz': arrival_hz,
            'header_span_hz': header_hz,
            'minimum_required_hz': self.minimum_hz,
            'first_header_stamp_ns': self.first_stamp_ns,
            'last_header_stamp_ns': self.last_stamp_ns,
            'invalid_stamps': self.invalid_stamps,
            'equal_stamps': self.equal_stamps,
            'backward_stamps': self.backward_stamps,
            'invalid_payloads': self.invalid_payloads,
            'payload_errors': self.payload_errors,
            'minimum_points': self.minimum_points,
            'maximum_points': self.maximum_points,
            'minimum_line': self.minimum_line,
            'maximum_line': self.maximum_line,
            'minimum_quaternion_norm': self.minimum_quaternion_norm,
            'maximum_quaternion_norm': self.maximum_quaternion_norm,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--duration', type=positive_seconds, default=30.0,
                        help='预热后实际统计秒数，默认 30')
    parser.add_argument('--warmup', type=nonnegative_seconds, default=5.0,
                        help='统计前等待初始化的秒数，默认 5')
    parser.add_argument('--input-only', action='store_true', help='只验收雷达和 IMU，不要求 FAST-LIO 输出')
    parser.add_argument('--output', type=Path, required=True, help='本次 JSON 结果文件路径')
    parser.add_argument('--scan-lines', type=int, default=4, help='有效 line 范围为 0 至此值减一，MID360 默认 4')
    # 保留标准 --ros-args，以便需要时通过 ROS2 参数重映射话题。
    args, ros_arguments = parser.parse_known_args()
    if args.scan_lines <= 0:
        parser.error('--scan-lines 必须大于 0')

    stats = {
        'lidar': StreamStats('/livox/lidar', 5.0),
        'imu': StreamStats('/livox/imu', 100.0),
    }
    if not args.input_only:
        stats.update({
            'cloud': StreamStats('/cloud_registered', 3.0),
            'odometry': StreamStats('/Odometry', 3.0),
        })

    started_utc = datetime.now(timezone.utc).isoformat()
    start = time.monotonic()
    measure_start = start + args.warmup
    deadline = measure_start + args.duration
    interrupted = False
    completed = False
    error = None
    node = None
    rclpy = None

    def in_window():
        """预热期间仍处理订阅，丢弃统计；只统计固定窗口内的新到消息。"""
        now = time.monotonic()
        return now if measure_start <= now <= deadline else None

    def lidar_callback(message):
        now = in_window()
        if now is None:
            return
        item = stats['lidar']
        item.receive(message, now)
        number = len(message.points)
        item.points(number)
        problems = []
        if number == 0 or int(message.point_num) <= 0:
            problems.append('empty_lidar_points')
        if number != int(message.point_num):
            problems.append('point_num_does_not_match_points')
        # 检查所有点的 line；不复制点云，也不把原始点存入 JSON。
        out_of_range = False
        for point in message.points:
            line = int(point.line)
            item.minimum_line = line if item.minimum_line is None else min(item.minimum_line, line)
            item.maximum_line = line if item.maximum_line is None else max(item.maximum_line, line)
            if not 0 <= line < args.scan_lines:
                out_of_range = True
        if out_of_range:
            problems.append('lidar_line_out_of_range')
        item.invalid(*problems)

    def imu_callback(message):
        now = in_window()
        if now is None:
            return
        item = stats['imu']
        item.receive(message, now)
        # MID360 可不提供姿态，因此不要求 IMU orientation 四元数有效。
        acceleration = message.linear_acceleration
        angular = message.angular_velocity
        if not all(math.isfinite(value) for value in (
                acceleration.x, acceleration.y, acceleration.z, angular.x, angular.y, angular.z)):
            item.invalid('nonfinite_imu_acceleration_or_angular_velocity')

    def cloud_callback(message):
        now = in_window()
        if now is None:
            return
        item = stats['cloud']
        item.receive(message, now)
        number = int(message.width) * int(message.height)
        item.points(number)
        if number <= 0 or not message.data or int(message.point_step) <= 0:
            item.invalid('empty_registered_cloud')
        elif (int(message.row_step) < int(message.width) * int(message.point_step)
              or int(message.row_step) * int(message.height) > len(message.data)):
            item.invalid('registered_cloud_data_shorter_than_dimensions')

    def odometry_callback(message):
        now = in_window()
        if now is None:
            return
        item = stats['odometry']
        item.receive(message, now)
        position = message.pose.pose.position
        quaternion = message.pose.pose.orientation
        values = (position.x, position.y, position.z,
                  quaternion.x, quaternion.y, quaternion.z, quaternion.w)
        if not all(math.isfinite(value) for value in values):
            item.invalid('nonfinite_odometry_pose')
            return
        # hypot 比平方后求和更不易发生浮点溢出。
        norm = math.hypot(*values[3:])
        if not math.isfinite(norm):
            item.invalid('nonfinite_odometry_quaternion_norm')
            return
        item.minimum_quaternion_norm = norm if item.minimum_quaternion_norm is None else min(item.minimum_quaternion_norm, norm)
        item.maximum_quaternion_norm = norm if item.maximum_quaternion_norm is None else max(item.maximum_quaternion_norm, norm)
        if norm <= 1e-6:
            item.invalid('zero_odometry_quaternion')

    try:
        # 在此导入以捕获未 source 环境或驱动消息未编译等明确错误。
        import rclpy as rclpy_module
        from rclpy.node import Node
        from rclpy.qos import qos_profile_sensor_data
        from livox_ros_driver2.msg import CustomMsg
        from nav_msgs.msg import Odometry
        from sensor_msgs.msg import Imu, PointCloud2

        rclpy = rclpy_module
        rclpy.init(args=ros_arguments)
        node = Node('livox_fastlio_stream_verifier')
        # BEST_EFFORT 订阅可匹配 RELIABLE 和 BEST_EFFORT 发布者。
        # 队列深度 10 给 200 Hz IMU 留出一点调度余量，不修改驱动 QoS。
        qos_profile_sensor_data.depth = 10
        subscriptions = [
            node.create_subscription(CustomMsg, '/livox/lidar', lidar_callback, qos_profile_sensor_data),
            node.create_subscription(Imu, '/livox/imu', imu_callback, qos_profile_sensor_data),
        ]
        if not args.input_only:
            subscriptions.extend([
                node.create_subscription(PointCloud2, '/cloud_registered', cloud_callback, qos_profile_sensor_data),
                node.create_subscription(Odometry, '/Odometry', odometry_callback, qos_profile_sensor_data),
            ])
        # 以订阅建立完毕为预热起点，避免导入耗时缩短实际测量。
        start = time.monotonic()
        measure_start = start + args.warmup
        deadline = measure_start + args.duration
        print(f'验收已开始：预热 {args.warmup:g} 秒，统计 {args.duration:g} 秒。', file=sys.stderr, flush=True)
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=min(0.2, max(0.0, deadline - time.monotonic())))
        completed = time.monotonic() >= deadline
    except KeyboardInterrupt:
        interrupted = True
        print('收到 Ctrl+C；保存已有统计，本次结果标记为未完成。', file=sys.stderr)
    except Exception as exception:
        # ROS 上下文被 Ctrl+C 关闭时，也可能抛出 ExternalShutdownException。
        interrupted = exception.__class__.__name__ == 'ExternalShutdownException'
        error = None if interrupted else f'{exception.__class__.__name__}: {exception}'
        if interrupted:
            print('ROS2 上下文已关闭；保存未完成统计。', file=sys.stderr)
        else:
            traceback.print_exc(file=sys.stderr)
    finally:
        # 只销毁本工具自己的节点，不停止驱动或 FAST-LIO。
        try:
            if node is not None:
                node.destroy_node()
            if rclpy is not None and rclpy.ok():
                rclpy.shutdown()
        except Exception as exception:
            traceback.print_exc(file=sys.stderr)
            if not interrupted:
                error = error or f'cleanup: {exception.__class__.__name__}: {exception}'

    # 异常或中断时按实际测量时间计算，并明确禁止将部分测试判为通过。
    elapsed = min(args.duration, max(0.0, time.monotonic() - measure_start))
    topic_results = {key: item.result(elapsed) for key, item in stats.items()}
    passed = completed and not interrupted and error is None and all(item['passed'] for item in topic_results.values())
    result = {
        'schema_version': 1,
        'started_utc': started_utc,
        'finished_utc': datetime.now(timezone.utc).isoformat(),
        'hostname': platform.node(),
        'input_only': args.input_only,
        'warmup_seconds': args.warmup,
        'requested_measurement_seconds': args.duration,
        'actual_measurement_seconds': elapsed,
        'scan_lines': args.scan_lines,
        'completed': completed,
        'interrupted': interrupted,
        'error': error,
        'passed': passed,
        'topics': topic_results,
        'scope': '实收频率、时间戳递增和基础数据有效性；不代表外参标定、建图精度或长期稳定性通过。',
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
    print(f'验收结果：{"通过" if passed else "未通过"}；JSON：{args.output}', file=sys.stderr)
    return 0 if passed else (130 if interrupted else 1)


if __name__ == '__main__':
    raise SystemExit(main())
