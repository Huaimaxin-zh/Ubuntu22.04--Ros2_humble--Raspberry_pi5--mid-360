# 用法：source ~/livox_runtime/env.sh，在当前终端加载驱动与FAST-LIO。
# 按基础ROS -> 驱动 -> FAST-LIO 的顺序加载，保证自定义消息类型可找到。
source /opt/ros/humble/setup.bash
source /home/xin/ws_livox/install/setup.bash
source /home/xin/ws_fastlio/install/setup.bash
# 用户安装的SDK动态库需要出现在动态链接器搜索路径中。
export LD_LIBRARY_PATH="/home/xin/livox_sdk2/lib:${LD_LIBRARY_PATH:-}"
# 默认同机运行使用域10；可在启动前通过LIVOX_ROS_DOMAIN_ID统一覆盖。
export ROS_DOMAIN_ID="${LIVOX_ROS_DOMAIN_ID:-10}"
export ROS_LOCALHOST_ONLY=0
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
