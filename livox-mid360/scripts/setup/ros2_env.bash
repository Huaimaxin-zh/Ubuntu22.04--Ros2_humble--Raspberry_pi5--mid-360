# 此文件由 ~/.bashrc 加载，只配置当前用户的 ROS2 Humble 环境。
# 先判断基础环境是否存在，避免安装前打开终端时出现报错。
if [ -r /opt/ros/humble/setup.bash ]; then
    # source 会把 ROS2 的命令路径、库路径和 Python 路径加入当前终端。
    source /opt/ros/humble/setup.bash
fi

# 工作空间编译成功后，可在使用时手动加载相应的 install/setup.bash。
# 例如：source ~/ws_livox/install/setup.bash
# 不在这里预设 DOMAIN、发现服务器或代理，后续按通信方案统一配置。
