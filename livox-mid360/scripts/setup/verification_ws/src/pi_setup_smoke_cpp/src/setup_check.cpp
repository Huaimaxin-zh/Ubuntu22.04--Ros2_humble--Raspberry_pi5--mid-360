// 引入 ROS2 C++ 节点和日志接口。
#include <rclcpp/rclcpp.hpp>

// 程序从 main 进入；ROS2 会读取标准命令行参数。
int main(int argc, char **argv)
{
  // 初始化 ROS2 的本进程上下文。
  rclcpp::init(argc, argv);
  // 创建一个只用于本机配置验证的节点。
  auto node = rclcpp::Node::make_shared("pi_setup_check");
  // 成功打印此行意味着 C++ 编译、链接、ROS2 初始化和日志均可用。
  RCLCPP_INFO(node->get_logger(), "PI5_HUMBLE_CPP_BUILD_OK");
  // 释放节点，然后正常关闭 ROS2 上下文。
  node.reset();
  rclcpp::shutdown();
  // 返回零表示程序正常结束。
  return 0;
}
