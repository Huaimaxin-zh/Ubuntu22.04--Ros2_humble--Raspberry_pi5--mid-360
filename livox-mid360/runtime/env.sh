# 用途：在“当前 Bash 终端”加载已经安装好的独立 Livox 环境。
# 正确用法：source ~/livox_runtime/env.sh；直接 bash 执行不会改变父终端。

# 独立运行目录；这是本次已验证的安装位置，不是 Git 仓库的位置。
_livox_runtime=/home/xin/livox_runtime

# 清除当前终端之前加载的 ROS/colcon/Python/动态库搜索路径。
# 这样不会混入原系统已损坏的 ROS；不会删除任何文件，也不会修改 .bashrc。
unset AMENT_PREFIX_PATH CMAKE_PREFIX_PATH COLCON_PREFIX_PATH PYTHONPATH LD_LIBRARY_PATH

# 先加载私有 ROS 基础依赖，为后面的驱动提供运行环境。
source "$_livox_runtime/ros-clean/opt/ros/humble/local_setup.bash"

# 再加载编译完成的 Livox 驱动包，使 ROS 能找到包和自定义消息类型。
source "$_livox_runtime/install/livox_ros_driver2/share/livox_ros_driver2/local_setup.bash"

# 给 Python 增加私有模块路径；冒号用于分隔多个搜索目录。
# 后面的 $PYTHONPATH 保留刚刚由干净 ROS 环境生成的路径。
export PYTHONPATH="$_livox_runtime/python-clean:$_livox_runtime/ubuntu-clean/usr/lib/python3/dist-packages:$_livox_runtime/ubuntu-clean/usr/lib/python3.10/dist-packages:$PYTHONPATH"

# 给动态链接器增加 SDK、BLAS、LAPACK 和其他私有动态库的搜索路径。
# export 表示稍后从本终端启动的子程序也能读到该变量。
export LD_LIBRARY_PATH="$_livox_runtime/sdk/lib:$_livox_runtime/ubuntu-clean/usr/lib/aarch64-linux-gnu/blas:$_livox_runtime/ubuntu-clean/usr/lib/aarch64-linux-gnu/lapack:$_livox_runtime/ubuntu-clean/usr/lib/aarch64-linux-gnu:$LD_LIBRARY_PATH"

# 指定 ROS2 使用 Fast DDS 的 C++ RMW 实现。
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp

# 同一个 ROS2 网络中的节点通常需要使用同一个域 ID；此次测试使用 10。
export ROS_DOMAIN_ID=10

# 0 表示不把 ROS2 通信限制在本机回环接口。
export ROS_LOCALHOST_ONLY=0

# 清除当前终端遗留的 Discovery Server、XML 和相关 QoS 配置。
# 这个启动环境默认用于本地采集；以后跨电脑通信时需另行配置发现方式。
unset ROS_DISCOVERY_SERVER FASTRTPS_DEFAULT_PROFILES_FILE FASTDDS_DEFAULT_PROFILES_FILE RMW_FASTRTPS_USE_QOS_FROM_XML

# 删除脚本内部的辅助变量，避免留在交互终端中；前面的路径已展开生效。
unset _livox_runtime
