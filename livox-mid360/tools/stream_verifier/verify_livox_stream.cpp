// ROS2 C++ 节点、订阅器、QoS 和执行器的接口。
#include <rclcpp/rclcpp.hpp>
// Livox 自定义点云消息，包含 point_num、timebase 和点数组。
#include <livox_ros_driver2/msg/custom_msg.hpp>
// 标准 IMU 消息，包含角速度和线加速度等字段。
#include <sensor_msgs/msg/imu.hpp>
// min/max 用于记录每帧点数范围。
#include <algorithm>
// chrono 用于计时，cmath 的 isfinite 用于检查 NaN 和无穷值。
#include <chrono>
#include <cmath>
// 固定宽度整数、终端输出和整数最大值。
#include <cstdint>
#include <iostream>
#include <limits>

// steady_clock 单调递增，不会因为系统校时而改变频率测量结果。
using Clock = std::chrono::steady_clock;

// 每种数据流各维护一份统计对象：点云一份、IMU 一份。
struct Stream {
  // 成功进入回调的消息数量。
  uint64_t count = 0;
  // 检查异常次数；同一条消息若有多个异常，可能累加多次。
  uint64_t invalid = 0;
  // 上一条消息自带的时间戳，单位为纳秒。
  int64_t last_stamp = 0;
  // 第一条和最后一条消息到达检查器的本地时刻。
  Clock::time_point first, last;

  // 每收到一条消息就调用这里，记录时戳、时间和数量。
  void record(int64_t stamp) {
    // 获取当前单调时钟的时刻。
    const auto now = Clock::now();
    // count 初始为 0，所以只在第一条消息记录起点。
    if (!count) first = now;
    // 时戳必须大于 0，而且从第二条开始必须严格增加。
    if (stamp <= 0 || (count && stamp <= last_stamp)) ++invalid;
    // 保留本次时戳，供下一条消息比较。
    last_stamp = stamp;
    // 更新最后接收时刻和总数。
    last = now;
    ++count;
  }

  // 返回首末接收之间的平均频率，单位 Hz；至少两条消息才有时间间隔。
  double rate() const {
    // N 条消息有 N-1 个间隔；duration<double> 把时间差转换成秒。
    return count > 1 ? (count - 1) / std::chrono::duration<double>(last - first).count() : 0.0;
  }
};

// 程序入口；argc/argv 允许 ROS2 解析终端传入的参数。
int main(int argc, char **argv) {
  // 初始化 ROS2 上下文，随后才能创建节点。
  rclcpp::init(argc, argv);
  // 创建检查节点；名字用于在 ROS2 图中识别这个程序。
  auto node = rclcpp::Node::make_shared("livox_native_installation_check");
  // 分别保存点云、IMU 统计，互不混算。
  Stream cloud, imu;
  // 前 5 秒持续收取消息但不统计，用于跳过启动积压。
  const auto warmup_until = Clock::now() + std::chrono::seconds(5);
  // 最小值从最大整数开始，收到第一帧时就会被替换；最大值从 0 开始。
  uint32_t min_points = std::numeric_limits<uint32_t>::max(), max_points = 0;
  // 累计实际检查过坐标的点数。
  uint64_t finite_points_checked = 0;
  // 使用适合实时传感器的 QoS；它也可与可靠发布者匹配。
  const auto qos = rclcpp::SensorDataQoS();

  // 创建 CustomMsg 订阅器。保存 cloud_sub，使订阅器在检查期间保持存活。
  auto cloud_sub = node->create_subscription<livox_ros_driver2::msg::CustomMsg>(
    // [&] 表示回调按引用使用外面的统计变量；ConstSharedPtr 避免复制消息。
    "/livox/lidar", qos, [&](const livox_ros_driver2::msg::CustomMsg::ConstSharedPtr msg) {
      // 预热期间直接返回；消息已经被接收，不会专门留着等统计开始。
      if (Clock::now() < warmup_until) return;
      // 秒乘十亿再加纳秒，得到完整消息时间戳。LL 表示长整数常量。
      cloud.record(int64_t(msg->header.stamp.sec) * 1000000000LL + msg->header.stamp.nanosec);
      // 点云必须非空，声明点数与数组长度一致，且设备 timebase 非零。
      if (!msg->point_num || msg->point_num != msg->points.size() || !msg->timebase) ++cloud.invalid;
      // 更新观测期间每帧点数的最小值和最大值。
      min_points = std::min(min_points, msg->point_num);
      max_points = std::max(max_points, msg->point_num);
      // 遍历本帧所有点，不只抽查第一点。
      for (const auto &point : msg->points) {
        // 坐标不能是 NaN 或正负无穷；零坐标仍属于有限值。
        if (!std::isfinite(point.x) || !std::isfinite(point.y) || !std::isfinite(point.z)) ++cloud.invalid;
        // 无论此点有效与否，都计入已检查点数。
        ++finite_points_checked;
      }
    });

  // 创建 IMU 订阅器；它与点云订阅器使用各自的消息类型和回调。
  auto imu_sub = node->create_subscription<sensor_msgs::msg::Imu>(
    "/livox/imu", qos, [&](const sensor_msgs::msg::Imu::ConstSharedPtr msg) {
      // 同样跳过前 5 秒，使两种统计窗口一致。
      if (Clock::now() < warmup_until) return;
      // 检查 IMU 时间戳，并累加消息数量。
      imu.record(int64_t(msg->header.stamp.sec) * 1000000000LL + msg->header.stamp.nanosec);
      // 将三轴角速度、三轴线加速度放到数组中，方便统一检查。
      const double values[] = {msg->angular_velocity.x, msg->angular_velocity.y, msg->angular_velocity.z,
        msg->linear_acceleration.x, msg->linear_acceleration.y, msg->linear_acceleration.z};
      // 检查六个数值是否有限；这里不判断标定精度或物理量是否准确。
      for (double value : values) if (!std::isfinite(value)) ++imu.invalid;
    });

  // 执行器负责从 ROS2 中取出就绪消息并调用上述回调。
  rclcpp::executors::SingleThreadedExecutor executor;
  // 把节点加入执行器，否则订阅回调不会由它执行。
  executor.add_node(node);
  // 总时长为 5 秒预热加 25 秒统计。
  const auto deadline = warmup_until + std::chrono::seconds(25);
  // 正常运行且没有超过结束时刻时，持续处理消息。
  while (rclcpp::ok() && Clock::now() < deadline) {
    // 一次处理就绪工作，最多等待 100 毫秒，之后可重新检查结束条件。
    executor.spin_once(std::chrono::milliseconds(100));
  }

  // 通过条件：消息数量足够、没有内容异常，且频率落在预设范围。
  // 这是本次采集检查，不代表完成了标定、时间同步或长期零丢包验证。
  const bool passed = cloud.count >= 100 && imu.count >= 2000 && !cloud.invalid && !imu.invalid &&
    cloud.rate() >= 8.0 && cloud.rate() <= 12.0 && imu.rate() >= 150.0 && imu.rate() <= 250.0;

  // 用 JSON 输出结果，既方便人在终端阅读，也方便保存到 evidence 目录。
  // << 表示把后面的内容依次写入标准输出，\n 表示换行。
  std::cout << "{\n  \"observer\": \"native_cpp\",\n"
    << "  \"warmup_seconds\": 5,\n  \"measurement_seconds\": 25,\n"
    << "  \"cloud_count\": " << cloud.count << ",\n"
    << "  \"cloud_rate_hz\": " << cloud.rate() << ",\n"
    << "  \"cloud_points_min\": " << (cloud.count ? min_points : 0) << ",\n"
    << "  \"cloud_points_max\": " << max_points << ",\n"
    << "  \"finite_points_checked\": " << finite_points_checked << ",\n"
    << "  \"invalid_clouds\": " << cloud.invalid << ",\n"
    << "  \"imu_count\": " << imu.count << ",\n"
    << "  \"imu_rate_hz\": " << imu.rate() << ",\n"
    << "  \"invalid_imus\": " << imu.invalid << ",\n"
    << "  \"passed\": " << (passed ? "true" : "false") << "\n}" << std::endl;

  // 检查结束后将节点移出执行器，释放程序使用的 ROS2 资源。
  executor.remove_node(node);
  node.reset();
  rclcpp::shutdown();
  // 告知 shell 检查是否通过：0 成功，1 未通过。
  return passed ? 0 : 1;
}
