# 要求 CMake 至少为 3.14，避免使用过旧版本配置项目。
cmake_minimum_required(VERSION 3.14)

# 定义项目名称；这个小工具只使用 C++，因此不启用 C 编译器。
project(livox_stream_verifier LANGUAGES CXX)

# 加载 ROS2 的 CMake 辅助工具，用来为目标配置依赖。
find_package(ament_cmake REQUIRED)
# rclcpp 提供 C++ 节点、订阅器和执行器。
find_package(rclcpp REQUIRED)
# Livox 驱动包提供 CustomMsg 点云消息类型。
find_package(livox_ros_driver2 REQUIRED)
# sensor_msgs 提供标准 IMU 消息类型。
find_package(sensor_msgs REQUIRED)

# 将源文件编译成名为 verify_livox_stream 的可执行程序。
add_executable(verify_livox_stream verify_livox_stream.cpp)
# 明确启用至少 C++14 的语言特性。
target_compile_features(verify_livox_stream PRIVATE cxx_std_14)
# 自动配置三个 ROS2 依赖包的头文件和链接库。
ament_target_dependencies(verify_livox_stream rclcpp livox_ros_driver2 sensor_msgs)

# cmake --install 时，把程序放到指定安装前缀下的 bin 目录。
install(TARGETS verify_livox_stream RUNTIME DESTINATION bin)
