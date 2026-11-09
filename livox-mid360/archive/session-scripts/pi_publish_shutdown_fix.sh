#!/usr/bin/env bash
# 中文说明：本文件仅保存此次现场补丁，不能一键安装或一键重建驱动。
# 它依赖 RAM 和持久目录中两份指定旧源码，/dev/shm 重启后消失。
# 补丁要求精确旧文本；修复后再次执行会因匹配数量不同停止，不可重复运行。
# 本脚本会改写两个副本的 lddc.cpp，不处理原 ~/ws_livox/src 工作区。
# Python 报错就停止 Shell，不继续后续操作。
set -e
# 下方 Python 从标准输入运行；带引号的 PY 标记禁止 Shell 提前解释内容。
python3 - <<'PY'
# Path 用于表示文件路径及读写文本。
from pathlib import Path
# 仅处理 RAM 构建副本和持久保存的源码副本，不改原工作区。
for root in (Path('/dev/shm/livox-recovery-xin/src/livox_ros_driver2'),Path('/home/xin/livox_runtime/src/livox_ros_driver2')):
    # 要修复的是点云分发实现文件。
    path=root/'src/lddc.cpp'
    # 读入完整文本，所有替换成功后才写回当前这一份文件。
    text=path.read_text()
    # 原循环只判断队列是否为空，没有检查退出请求。
    old='while(!QueueIsEmpty(queue))'
    # 预期旧版本共有三个相同循环；数量不同表示版本或补丁状态不符合前提。
    if text.count(old)!=3:
        # 立即停止，避免修改未知版本；本轮当前文件尚未写回。
        raise SystemExit('Unexpected point cloud publication loops: '+str(text.count(old)))
    # 只修改 PointCloud2 和 CustomMsg 发布函数，保留另外的 PCL 分支循环。
    for name in ('PublishPointcloud2', 'PublishCustomPointcloud'):
        # 先定位目标函数，避免误改其他函数中的相同循环。
        pos=text.index('void Lddc::'+name+'(')
        # 从目标函数之后找第一个旧循环条件。
        loop=text.index(old,pos)
        # 仅替换一次：有退出请求时，即使持续入队也能结束发布循环。
        text=text[:loop]+text[loop:].replace(old,'while(!lds_->IsRequestExit() && !QueueIsEmpty(queue))',1)
    # 写回这份源码的两个循环修复；此操作不会自动编译或启动驱动。
    path.write_text(text)
# 只有两份源码都处理完成后才输出此提示。
print('Both cloud publication loops now honor shutdown')
PY
