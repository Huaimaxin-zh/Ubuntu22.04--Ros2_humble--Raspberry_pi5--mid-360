"""检查器入口：运行原生 C++ 工具，避免 Python 逐点解析密集点云。"""

# Path 用于按文件位置构造路径，而不依赖你当前在哪个目录运行命令。
from pathlib import Path

# subprocess 用于启动另一个程序并等待它结束。
import subprocess

# __file__ 是本脚本路径；resolve() 转成绝对路径；parent 得到所在目录。
# / 运算符在 Path 中表示拼接路径，因此目标是“脚本所在目录/bin/检查器”。
# 这个文件按原运行布局放在 ~/livox_runtime 中时，才能找到已安装的 bin。
observer = Path(__file__).resolve().parent / 'bin' / 'verify_livox_stream'

# 列表形式传参，不经过 shell 拼接；call 会等待检查器完成并返回退出码。
# SystemExit 把退出码传回终端：0 通常表示成功，非零表示检查未通过或出错。
raise SystemExit(subprocess.call([str(observer)]))
