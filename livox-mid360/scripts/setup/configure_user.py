#!/usr/bin/env python3
"""备份并设置 xin 用户的 Bash 环境；不需要管理员权限。"""

# pathlib 用于明确操作用户家目录中的文件。
from pathlib import Path
# datetime 用于生成不会覆盖旧备份的文件名。
from datetime import datetime, timezone
# shutil.copy2 保留备份文件的时间等基础属性。
import shutil

# 只允许在已确认的树莓派 xin 家目录下执行。
home = Path.home()
if home != Path('/home/xin'):
    raise SystemExit(f'Unexpected home directory: {home}')

# 使用单独文件放 ROS2 设置，保留原有 .bashrc 内容和结构。
bashrc = home / '.bashrc'
marker = '# ROS2 Humble environment (pi_setup)'
addition = '\n' + marker + '\n[ ! -r "$HOME/pi_setup/ros2_env.bash" ] || source "$HOME/pi_setup/ros2_env.bash"\n'
# 读取原始文件；若之前已经设置，重复执行也不会重复追加。
text = bashrc.read_text(encoding='utf-8')
if marker not in text:
    # 备份写入 pi_setup，避免和现有 shell 文件混淆。
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = home / 'pi_setup' / f'bashrc-before-{stamp}'
    shutil.copy2(bashrc, backup)
    # 以追加方式保留所有原有设置。
    with bashrc.open('a', encoding='utf-8') as output:
        output.write(addition)
    print(f'Bash configuration backup: {backup}')

# 提前建立工作空间的源码目录；不生成虚假的 build/install 结果。
for workspace in ('dev_ws', 'ws_livox'):
    (home / workspace / 'src').mkdir(parents=True, exist_ok=True)
print('User environment configured.')
