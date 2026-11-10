# 指定本示例需要的 CMake 最低版本。
cmake_minimum_required(VERSION 3.8)
# 工程名必须与 package.xml 中的包名一致。
project(pi_setup_smoke_cpp)
# 找到 ROS2 的 CMake 构建工具。
find_package(ament_cmake REQUIRED)
# 找到 ROS2 C++ 客户端库。
find_package(rclcpp REQUIRED)
# 将一份源代码编译为名为 setup_check 的可执行文件。
add_executable(setup_check src/setup_check.cpp)
# 自动为可执行文件设置 rclcpp 的头文件路径和链接库。
ament_target_dependencies(setup_check rclcpp)
# ROS2 约定将可执行文件安装在 lib/包名，ros2 run 据此查找。
install(TARGETS setup_check DESTINATION lib/${PROJECT_NAME})
# 导出包信息，供 ROS2 在加载工作空间后发现此包。
ament_package()
