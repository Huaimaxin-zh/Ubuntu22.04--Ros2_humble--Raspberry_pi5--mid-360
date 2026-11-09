#!/usr/bin/env bash
# 中文说明：本文件仅保存此次现场补丁，不能一键安装或一键重建驱动。
# 它依赖 RAM 和持久目录中的两份指定旧源码；/dev/shm 重启后消失。
# 精确旧文本匹配用于防止误改；修复后再次执行会报错，不可重复运行。
# 原 ~/ws_livox/src 不在目标范围；修改副本后仍需重新编译，才会影响程序。
# Python 失败就停止 Shell，避免输出虚假的完成状态。
set -e
# 从此处到 PY 标记运行 Python；引号禁止 Shell 解释其中变量或反斜杠。
python3 - <<'PY'
# Path 用来定位和读写源码文件。
from pathlib import Path
# 只处理 RAM 构建副本及用户目录中保存的源码副本。
roots=[Path('/dev/shm/livox-recovery-xin/src/livox_ros_driver2'),Path('/home/xin/livox_runtime/src/livox_ros_driver2')]
# 下方 old 是必须逐字匹配的原 C++ 代码，不是 Python 此刻执行的线程操作。
# 原顺序只设置退出标志后等待线程，无数据时两个线程仍可能阻塞在信号量 Wait。
old='''DriverNode::~DriverNode() {
  lddc_ptr_->lds_->RequestExit();
  exit_signal_.set_value();
  pointclouddata_poll_thread_->join();
  imudata_poll_thread_->join();
}'''
# 下方 new 是要写入源码的完整新析构函数，字符串原文保持不动。
# set_value 先通知退出 future，防止唤醒后的线程再次进入等待。
# 检查指针非空后，RequestExit 设置退出标志，两个 Signal 唤醒点云和 IMU 等待线程。
# 指针和 joinable 检查后才 join；等待完成后，再由后续析构清理 SDK。
new='''DriverNode::~DriverNode() {
  // Make the exit future ready before waking poll threads that have no data.
  exit_signal_.set_value();
  if (lddc_ptr_ && lddc_ptr_->lds_) {
    lddc_ptr_->lds_->RequestExit();
    lddc_ptr_->lds_->pcd_semaphore_.Signal();
    lddc_ptr_->lds_->imu_semaphore_.Signal();
  }
  if (pointclouddata_poll_thread_ && pointclouddata_poll_thread_->joinable()) {
    pointclouddata_poll_thread_->join();
  }
  if (imudata_poll_thread_ && imudata_poll_thread_->joinable()) {
    imudata_poll_thread_->join();
  }
}'''
# 逐份处理两个指定副本；不是扫描或批量修改整个用户目录。
for root in roots:
    # 先修复 DriverNode 的析构函数。
    path=root/'src/driver_node.cpp'
    # 读取当前完整文本；此时尚未写回这个文件。
    text=path.read_text()
    # 只允许旧函数恰好出现一次，版本不符或已修复都必须停止。
    if text.count(old)!=1:
        # 报出不符合前提的文件路径，供人工检查。
        raise SystemExit('Unexpected destructor content: '+str(path))
    # 将唯一旧函数替换成新函数，写回当前 cpp 副本。
    path.write_text(text.replace(old,new,1))
    # 再处理跨线程共享的退出标志声明。
    path=root/'src/lds.h'
    # 读取当前完整文本；此时尚未写回这个文件。
    text=path.read_text()
    # 仍然要求匹配精确旧声明，避免对未知版本重复应用补丁。
    if text.count('volatile bool request_exit_;')!=1:
        # 声明数量异常时停止；注意之前的 cpp 修改可能已经完成，所以不是事务式补丁。
        raise SystemExit('Unexpected exit flag content')
    # std::atomic 需要相应头文件；已经包含时不再重复添加。
    if '#include <atomic>' not in text:
        # 找到第一个 include 的位置，保留其余布局。
        pos=text.index('#include')
        # 在已有 include 前加入 atomic 头文件。
        text=text[:pos]+'#include <atomic>\n'+text[pos:]
    # 把 volatile bool 改成 std::atomic<bool>，消除退出标志的跨线程数据竞争。
    path.write_text(text.replace('volatile bool request_exit_;','std::atomic<bool> request_exit_;',1))
# 所有指定目标都修复后才提示成功；本脚本不会启动雷达或重新编译。
print('Fixed disconnected-radar shutdown in task copies only')
PY
