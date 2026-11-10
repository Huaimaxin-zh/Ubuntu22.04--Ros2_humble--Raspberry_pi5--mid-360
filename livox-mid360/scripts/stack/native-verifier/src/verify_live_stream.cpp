// 低开销 C++ 实收验收：避免 Python 把每个 CustomPoint 转为对象的性能开销。
// 本程序只订阅，不启动/停止驱动，不保存地图，不保留原始点云。
#include <rclcpp/rclcpp.hpp>
#include <livox_ros_driver2/msg/custom_msg.hpp>
#include <sensor_msgs/msg/imu.hpp>
#include <sensor_msgs/msg/point_cloud2.hpp>
#include <nav_msgs/msg/odometry.hpp>
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

using Clock = std::chrono::steady_clock;
using Time = Clock::time_point;

// JSON 文本转义；所有输出都是计数/统计，不包含原始雷达点数据。
std::string json_quote(const std::string &text) {
  std::ostringstream out;
  out << '"';
  for (unsigned char c : text) {
    if (c == '"' || c == '\\') out << '\\' << c;
    else if (c == '\n') out << "\\n";
    else if (c == '\r') out << "\\r";
    else if (c == '\t') out << "\\t";
    else if (c < 32) out << "\\u" << std::hex << std::setw(4) << std::setfill('0') << int(c) << std::dec;
    else out << c;
  }
  return out.str() + '"';
}
std::string number(double value) {
  if (!std::isfinite(value)) return "null";
  std::ostringstream out;
  out << std::setprecision(12) << value;
  return out.str();
}
const char *boolean(bool value) { return value ? "true" : "false"; }

struct Options {
  double duration = 30.0, warmup = 5.0;
  int scan_lines = 4;
  bool input_only = false;
  std::string output;
};

// 每条流保留时间戳用于对齐核查，绝不保存原始消息和点云数组。
struct Stream {
  std::string key, topic, type;
  double minimum_hz;
  uint64_t count = 0, invalid_stamps = 0, equal_stamps = 0, backward_stamps = 0;
  uint64_t invalid_payloads = 0, empty_messages = 0, count_mismatch = 0;
  uint64_t invalid_xyz = 0, xyz_checked = 0, nonzero_xyz = 0, invalid_lines = 0;
  uint64_t nonfinite_imu = 0, nonfinite_pose = 0, nonunit_quaternion = 0;
  uint64_t min_points = std::numeric_limits<uint64_t>::max(), max_points = 0;
  int min_line = 256, max_line = -1;
  double min_quaternion = std::numeric_limits<double>::infinity(), max_quaternion = 0;
  double min_acceleration = std::numeric_limits<double>::infinity(), max_acceleration = 0;
  int64_t first_stamp = 0, last_stamp = 0;
  Time first_arrival{}, last_arrival{};
  std::vector<int64_t> stamps;
  std::vector<rclcpp::TopicEndpointInfo> publishers;

  Stream(std::string key_, std::string topic_, std::string type_, double minimum_hz_)
      : key(std::move(key_)), topic(std::move(topic_)), type(std::move(type_)), minimum_hz(minimum_hz_) {}

  void receive(const builtin_interfaces::msg::Time &stamp, Time now) {
    if (!count) first_arrival = now;
    last_arrival = now;
    ++count;
    const int64_t value = int64_t(stamp.sec) * 1000000000LL + stamp.nanosec;
    if (stamp.sec < 0 || stamp.nanosec >= 1000000000U || value <= 0) {
      ++invalid_stamps;
      return;
    }
    if (last_stamp) {
      if (value == last_stamp) ++equal_stamps;
      if (value < last_stamp) ++backward_stamps;
    } else first_stamp = value;
    last_stamp = value;
    stamps.push_back(value);
  }
  void points(uint64_t size) {
    min_points = std::min(min_points, size);
    max_points = std::max(max_points, size);
  }
  bool xyz(double x, double y, double z) {
    ++xyz_checked;
    if (!std::isfinite(x) || !std::isfinite(y) || !std::isfinite(z)) {
      ++invalid_xyz;
      return false;
    }
    if (x != 0 || y != 0 || z != 0) ++nonzero_xyz;
    return true;
  }
  double rate(double elapsed) const { return elapsed > 0 ? count / elapsed : 0; }
  bool graph_ok() const { return publishers.size() == 1 && publishers.front().topic_type() == type; }
  bool passed(double elapsed) const {
    const bool geometry_ok = (key != "lidar" && key != "cloud") || (xyz_checked && nonzero_xyz);
    return count >= 2 && rate(elapsed) >= minimum_hz && !invalid_stamps && !equal_stamps &&
      !backward_stamps && !invalid_payloads && geometry_ok && graph_ok();
  }
  std::string json(double elapsed) const {
    const double span = count > 1 ? std::chrono::duration<double>(last_arrival - first_arrival).count() : 0;
    std::ostringstream out;
    out << "{\"topic\":" << json_quote(topic) << ",\"expected_type\":" << json_quote(type)
      << ",\"passed\":" << boolean(passed(elapsed))
      << ",\"received_samples\":" << count << ",\"received_hz\":" << number(rate(elapsed))
      << ",\"arrival_span_hz\":" << (span > 0 ? number((count - 1) / span) : "null")
      << ",\"header_span_hz\":" << (last_stamp > first_stamp ? number((count - 1) * 1e9 / (last_stamp - first_stamp)) : "null")
      << ",\"minimum_required_hz\":" << number(minimum_hz)
      << ",\"first_header_stamp_ns\":" << first_stamp << ",\"last_header_stamp_ns\":" << last_stamp
      << ",\"invalid_stamps\":" << invalid_stamps << ",\"equal_stamps\":" << equal_stamps
      << ",\"backward_stamps\":" << backward_stamps << ",\"invalid_payloads\":" << invalid_payloads
      << ",\"minimum_points\":" << (min_points == std::numeric_limits<uint64_t>::max() ? "null" : std::to_string(min_points))
      << ",\"maximum_points\":" << max_points << ",\"minimum_line\":" << (max_line < 0 ? "null" : std::to_string(min_line))
      << ",\"maximum_line\":" << (max_line < 0 ? "null" : std::to_string(max_line))
      << ",\"minimum_quaternion_norm\":" << number(min_quaternion)
      << ",\"maximum_quaternion_norm\":" << (std::isfinite(min_quaternion) ? number(max_quaternion) : "null")
      << ",\"acceleration_norm_min\":" << number(min_acceleration)
      << ",\"acceleration_norm_max\":" << (std::isfinite(min_acceleration) ? number(max_acceleration) : "null")
      << ",\"xyz_checked\":" << xyz_checked << ",\"nonzero_xyz\":" << nonzero_xyz
      << ",\"payload_errors\":{\"empty\":" << empty_messages << ",\"point_num_mismatch\":" << count_mismatch
      << ",\"nonfinite_xyz\":" << invalid_xyz << ",\"line_out_of_range\":" << invalid_lines
      << ",\"nonfinite_imu\":" << nonfinite_imu << ",\"nonfinite_pose\":" << nonfinite_pose
      << ",\"nonunit_quaternion\":" << nonunit_quaternion << "}"
      << ",\"expected_publisher_count\":1,\"publisher_count\":" << publishers.size() << ",\"publishers\":[";
    for (size_t index = 0; index < publishers.size(); ++index) {
      if (index) out << ',';
      const auto &publisher = publishers[index];
      out << "{\"node_name\":" << json_quote(publisher.node_name()) << ",\"node_namespace\":"
          << json_quote(publisher.node_namespace()) << ",\"topic_type\":" << json_quote(publisher.topic_type()) << '}';
    }
    return out.str() + "]}";
  }
};

// 注册点云采用字段偏移读取，避免未对齐的 reinterpret_cast 和不必要的数据复制。
bool coordinate(const sensor_msgs::msg::PointCloud2 &message, size_t base,
                const sensor_msgs::msg::PointField &field, double &value) {
  const size_t size = field.datatype == sensor_msgs::msg::PointField::FLOAT32 ? 4 :
                      field.datatype == sensor_msgs::msg::PointField::FLOAT64 ? 8 : 0;
  if (!size || field.count != 1 || uint64_t(field.offset) + size > message.point_step ||
      base + field.offset + size > message.data.size()) return false;
  std::array<uint8_t, 8> bytes{};
  std::memcpy(bytes.data(), message.data.data() + base + field.offset, size);
  const uint16_t host = 1;
  const bool little_endian = *reinterpret_cast<const uint8_t *>(&host) == 1;
  if (bool(message.is_bigendian) == little_endian) std::reverse(bytes.begin(), bytes.begin() + size);
  if (size == 4) { float result; std::memcpy(&result, bytes.data(), size); value = result; }
  else std::memcpy(&value, bytes.data(), size);
  return true;
}

struct Alignment {
  bool passed = false;
  double maximum = std::numeric_limits<double>::infinity(), latest = std::numeric_limits<double>::quiet_NaN();
  Alignment(const Stream &left, const Stream &right) {
    if (left.stamps.empty() || right.stamps.empty()) return;
    std::vector<int64_t> ordered = right.stamps;
    std::sort(ordered.begin(), ordered.end());
    maximum = 0;
    for (const auto stamp : left.stamps) {
      auto after = std::lower_bound(ordered.begin(), ordered.end(), stamp);
      int64_t difference = std::numeric_limits<int64_t>::max();
      if (after != ordered.end()) difference = std::min<int64_t>(difference, std::llabs(*after - stamp));
      if (after != ordered.begin()) difference = std::min<int64_t>(difference, std::llabs(*std::prev(after) - stamp));
      maximum = std::max(maximum, difference / 1e9);
    }
    latest = (left.stamps.back() - right.stamps.back()) / 1e9;
    passed = maximum <= 0.25;
  }
  std::string json() const {
    return "{\"passed\":" + std::string(boolean(passed)) + ",\"maximum_nearest_difference_seconds\":" +
      number(maximum) + ",\"latest_left_minus_right_seconds\":" + number(latest) + ",\"tolerance_seconds\":0.25}";
  }
};

int main(int argc, char **argv) {
  Options options;
  try {
    const auto arguments = rclcpp::remove_ros_arguments(argc, argv);
    for (size_t index = 1; index < arguments.size(); ++index) {
      const auto &argument = arguments[index];
      if (argument == "--input-only") options.input_only = true;
      else if (argument == "--help") {
        std::cout << "verify_live_stream_native --output result.json [--input-only] [--duration 30] [--warmup 5] [--scan-lines 4]\n";
        return 0;
      } else if (index + 1 < arguments.size()) {
        if (argument == "--output") options.output = arguments[++index];
        else if (argument == "--duration") options.duration = std::stod(arguments[++index]);
        else if (argument == "--warmup") options.warmup = std::stod(arguments[++index]);
        else if (argument == "--scan-lines") options.scan_lines = std::stoi(arguments[++index]);
        else throw std::runtime_error("Unknown argument: " + argument);
      } else throw std::runtime_error("Missing argument value: " + argument);
    }
    if (options.output.empty() || !std::isfinite(options.duration) || options.duration <= 0 || options.duration > 600 ||
        !std::isfinite(options.warmup) || options.warmup < 0 || options.warmup > 120 || options.scan_lines <= 0)
      throw std::runtime_error("Require --output, duration in (0,600], warmup in [0,120], scan-lines > 0");
  } catch (const std::exception &exception) {
    std::cerr << exception.what() << '\n';
    return 2;
  }

  Stream lidar("lidar", "/livox/lidar", "livox_ros_driver2/msg/CustomMsg", 5.0);
  Stream imu("imu", "/livox/imu", "sensor_msgs/msg/Imu", 100.0);
  Stream cloud("cloud", "/cloud_registered", "sensor_msgs/msg/PointCloud2", 3.0);
  Stream odometry("odometry", "/Odometry", "nav_msgs/msg/Odometry", 3.0);
  std::vector<Stream *> streams{&lidar, &imu};
  if (!options.input_only) { streams.push_back(&cloud); streams.push_back(&odometry); }
  bool completed = false, interrupted = false;
  std::string error;
  Time measure_start = Clock::now(), deadline = measure_start;
  double elapsed = 0;
  try {
    rclcpp::init(argc, argv);
    auto node = rclcpp::Node::make_shared("livox_fastlio_native_stream_verifier");
    auto qos = rclcpp::SensorDataQoS().keep_last(20);
    // 预热期间仍接收并立即丢弃统计；不把启动积压消息当作正常速率。
    auto active = [&]() { const auto now = Clock::now(); return now >= measure_start && now <= deadline; };
    auto lidar_sub = node->create_subscription<livox_ros_driver2::msg::CustomMsg>(
      lidar.topic, qos, [&](livox_ros_driver2::msg::CustomMsg::ConstSharedPtr message) {
        if (!active()) return;
        lidar.receive(message->header.stamp, Clock::now());
        lidar.points(message->points.size());
        bool invalid = false;
        if (message->points.empty() || !message->point_num) { ++lidar.empty_messages; invalid = true; }
        if (message->point_num != message->points.size()) { ++lidar.count_mismatch; invalid = true; }
        for (const auto &point : message->points) {
          if (!lidar.xyz(point.x, point.y, point.z)) invalid = true;
          const int line = point.line;
          lidar.min_line = std::min(lidar.min_line, line); lidar.max_line = std::max(lidar.max_line, line);
          if (line < 0 || line >= options.scan_lines) { ++lidar.invalid_lines; invalid = true; }
        }
        if (invalid) ++lidar.invalid_payloads;
      });
    auto imu_sub = node->create_subscription<sensor_msgs::msg::Imu>(
      imu.topic, qos, [&](sensor_msgs::msg::Imu::ConstSharedPtr message) {
        if (!active()) return;
        imu.receive(message->header.stamp, Clock::now());
        const double values[] = {message->linear_acceleration.x, message->linear_acceleration.y, message->linear_acceleration.z,
                                message->angular_velocity.x, message->angular_velocity.y, message->angular_velocity.z};
        if (!std::all_of(std::begin(values), std::end(values), [](double value) { return std::isfinite(value); })) {
          ++imu.invalid_payloads; ++imu.nonfinite_imu;
        } else {
          // 官方驱动可能使用 g 单位；这里只记录范数，不硬性要求 9.81。
          const double norm = std::hypot(std::hypot(values[0], values[1]), values[2]);
          if (std::isfinite(norm)) { imu.min_acceleration = std::min(imu.min_acceleration, norm); imu.max_acceleration = std::max(imu.max_acceleration, norm); }
          else { ++imu.invalid_payloads; ++imu.nonfinite_imu; }
        }
      });
    rclcpp::Subscription<sensor_msgs::msg::PointCloud2>::SharedPtr cloud_sub;
    rclcpp::Subscription<nav_msgs::msg::Odometry>::SharedPtr odometry_sub;
    if (!options.input_only) {
      cloud_sub = node->create_subscription<sensor_msgs::msg::PointCloud2>(
        cloud.topic, qos, [&](sensor_msgs::msg::PointCloud2::ConstSharedPtr message) {
          if (!active()) return;
          cloud.receive(message->header.stamp, Clock::now());
          const uint64_t count = uint64_t(message->width) * message->height;
          cloud.points(count);
          if (!count || !message->point_step || message->data.empty() ||
              uint64_t(message->row_step) < uint64_t(message->width) * message->point_step ||
              uint64_t(message->row_step) * message->height > message->data.size()) {
            ++cloud.invalid_payloads; ++cloud.empty_messages; return;
          }
          std::array<const sensor_msgs::msg::PointField *, 3> fields{{nullptr, nullptr, nullptr}};
          for (const auto &field : message->fields) {
            if (field.name == "x") fields[0] = &field;
            if (field.name == "y") fields[1] = &field;
            if (field.name == "z") fields[2] = &field;
          }
          if (!fields[0] || !fields[1] || !fields[2]) { ++cloud.invalid_payloads; return; }
          bool invalid = false;
          // 注册点云每帧均匀抽样最多512点，包含首尾，不复制消息内容。
          const uint64_t samples = std::min<uint64_t>(count, 512);
          for (uint64_t sample = 0; sample < samples; ++sample) {
            const uint64_t index = samples > 1 ? sample * (count - 1) / (samples - 1) : 0;
            const size_t base = size_t(index / message->width) * message->row_step + size_t(index % message->width) * message->point_step;
            double x, y, z;
            if (!coordinate(*message, base, *fields[0], x) || !coordinate(*message, base, *fields[1], y) || !coordinate(*message, base, *fields[2], z)) {
              invalid = true; break;
            }
            if (!cloud.xyz(x, y, z)) invalid = true;
          }
          if (invalid) ++cloud.invalid_payloads;
        });
      odometry_sub = node->create_subscription<nav_msgs::msg::Odometry>(
        odometry.topic, qos, [&](nav_msgs::msg::Odometry::ConstSharedPtr message) {
          if (!active()) return;
          odometry.receive(message->header.stamp, Clock::now());
          const auto &p = message->pose.pose.position; const auto &q = message->pose.pose.orientation;
          const double values[] = {p.x, p.y, p.z, q.x, q.y, q.z, q.w};
          if (!std::all_of(std::begin(values), std::end(values), [](double value) { return std::isfinite(value); })) {
            ++odometry.invalid_payloads; ++odometry.nonfinite_pose; return;
          }
          const double norm = std::hypot(std::hypot(q.x, q.y), std::hypot(q.z, q.w));
          if (!std::isfinite(norm) || std::abs(norm - 1.0) > 0.01) { ++odometry.invalid_payloads; ++odometry.nonunit_quaternion; }
          if (std::isfinite(norm)) { odometry.min_quaternion = std::min(odometry.min_quaternion, norm); odometry.max_quaternion = std::max(odometry.max_quaternion, norm); }
        });
    }
    measure_start = Clock::now() + std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double>(options.warmup));
    deadline = measure_start + std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double>(options.duration));
    rclcpp::executors::SingleThreadedExecutor executor;
    executor.add_node(node);
    std::cerr << "Native C++ verifier: warmup=" << options.warmup << "s measurement=" << options.duration << "s\n";
    while (rclcpp::ok() && Clock::now() < deadline) executor.spin_once(std::chrono::milliseconds(10));
    completed = Clock::now() >= deadline;
    interrupted = !rclcpp::ok() && !completed;
    elapsed = std::min(options.duration, std::max(0.0, std::chrono::duration<double>(Clock::now() - measure_start).count()));
    for (auto *stream : streams) stream->publishers = node->get_publishers_info_by_topic(stream->topic);
    executor.remove_node(node);
  } catch (const std::exception &exception) {
    error = exception.what();
    std::cerr << "Native verifier error: " << error << '\n';
    elapsed = std::min(options.duration, std::max(0.0, std::chrono::duration<double>(Clock::now() - measure_start).count()));
  }
  if (rclcpp::ok()) rclcpp::shutdown();
  const Alignment input_alignment(lidar, imu), cloud_alignment(cloud, lidar), odometry_alignment(odometry, cloud);
  bool passed = completed && !interrupted && error.empty() && input_alignment.passed;
  for (const auto *stream : streams) passed = passed && stream->passed(elapsed);
  if (!options.input_only) passed = passed && cloud_alignment.passed && odometry_alignment.passed;
  const auto now = std::time(nullptr);
  std::ostringstream result;
  result << "{\n\"schema_version\":1,\"observer\":\"native_cpp\",\"finished_utc\":\"" << std::put_time(std::gmtime(&now), "%FT%TZ") << "\","
    << "\n\"passed\":" << boolean(passed) << ",\"completed\":" << boolean(completed) << ",\"interrupted\":" << boolean(interrupted)
    << ",\"error\":" << (error.empty() ? "null" : json_quote(error)) << ",\"input_only\":" << boolean(options.input_only)
    << ",\"warmup_seconds\":" << number(options.warmup) << ",\"requested_measurement_seconds\":" << number(options.duration)
    << ",\"actual_measurement_seconds\":" << number(elapsed) << ",\"scan_lines\":" << options.scan_lines << ",\n\"topics\":{";
  for (size_t index = 0; index < streams.size(); ++index) {
    if (index) result << ',';
    result << '\n' << json_quote(streams[index]->key) << ':' << streams[index]->json(elapsed);
  }
  result << "},\n\"time_alignment\":{\"lidar_to_imu\":" << input_alignment.json();
  if (!options.input_only) result << ",\"registered_cloud_to_lidar\":" << cloud_alignment.json()
    << ",\"odometry_to_registered_cloud\":" << odometry_alignment.json();
  result << "},\n\"scope\":\"Actual reception, monotonic timestamps and basic finite geometry; not calibration, mapping accuracy or long-term stability.\","
    << "\n\"geometry_sampling\":\"All received CustomMsg XYZ and line values; up to 512 registered cloud XYZ per frame. No raw point cloud retained.\"\n}\n";
  try {
    const std::filesystem::path path(options.output);
    if (!path.parent_path().empty()) std::filesystem::create_directories(path.parent_path());
    std::ofstream output(path);
    output.exceptions(std::ios::badbit | std::ios::failbit);
    output << result.str();
    output.close();
  } catch (const std::exception &exception) {
    std::cerr << "Cannot save JSON: " << exception.what() << '\n';
    std::cout << result.str();
    return 1;
  }
  std::cout << result.str();
  return passed ? 0 : interrupted ? 130 : 1;
}
