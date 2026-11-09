# VS Code Remote-SSH 连接树莓派卡在初始化：故障记录

日期：2026-11-09（北京时间）

状态：已解决。2026-11-09 19:07（北京时间）已连接到远程工作区，文件列表、脚本和远程终端均已加载。

## 1. 现象与环境

Windows 上的 VS Code 通过 Remote-SSH 连接树莓派时，左下角长期显示“正在打开远程”，右下角显示“正在初始化 VS Code 服务器”。有时出现密码输入框，有时日志已经显示 `Exec server ... created and cached`，但仍打不开远程文件夹。

本次连接信息：

| 项目 | 本次值 |
| --- | --- |
| Windows 端编辑器 | VS Code 1.143.0 |
| Remote-SSH 扩展 | 0.128.0 |
| SSH 客户端 | Windows OpenSSH 9.5p2 |
| SSH 连接别名 | `raspberrypi-livox` |
| 树莓派登录账号与管理地址 | `xin@192.168.0.103` |
| 树莓派系统与架构 | Ubuntu 22.04 / aarch64 |
| 希望打开的目录 | `/home/xin/livox_runtime` |

这里使用树莓派的 Wi-Fi 管理地址连接，不使用雷达地址 `192.168.123.20` 或雷达专用接收地址 `192.168.123.4`。

## 2. 日志证明了什么

### 2.1 密码提示与后续阻塞是两件事

`18:16:49` 的日志已经记录密码响应，随后安装程序在树莓派运行。因此，那一轮的长期等待不能只解释为“还没输密码”。重新加载后的 `18:57` 连接则确实重新停在密码输入框；新连接可能再次要求认证。

### 2.2 CLI 启动成功不代表完整服务已经装好

本次默认使用 exec server 模式。连接过程至少涉及两层：

```text
Windows VS Code
    │ SSH 登录与端口转发
    ▼
树莓派上的 VS Code CLI / exec server
    │ 继续下载、准备真正的远程编辑服务
    ▼
完整 VS Code Server
    │ 管理连接、远程扩展、文件访问、终端
    ▼
打开远程工作区
```

`18:17:19` 的日志显示 CLI 解压成功、远端端口监听、端口转发与 exec server 创建成功。这只能证明前面的步骤完成，不能单凭这几行就判断远程编辑环境已经可用。

随后，Windows renderer 日志显示管理连接（`Management`）和扩展主机连接（`ExtensionHost`）一直没有建立。`18:20:38` 又出现 `read ECONNRESET`，SSH 输出 `client_loop: send disconnect: Connection reset`。窗口直到重新加载时才取消这些等待。

### 2.3 真正的后续下载失败

进一步查看树莓派的 `agent-host-stable.log`，发现完整远程服务包预期大小为 **223,567,216 字节**，下载到 **73,686,160 字节，约 33%** 时出现：

```text
error decoding response body
```

因此，本次有直接证据支持的关键阻碍是：**CLI 已起来，但后续完整服务包下载中断，没有完成可用的 VS Code Server 安装。** 单纯继续等待不能保证恢复。

该错误说明下载响应体处理失败；现有证据不足以进一步确定是网络中断、下载链路或其他具体因素。不能据此断定 SD 卡损坏，也不能把前期雷达驱动问题直接当作本次原因。

`PendingMigrationError: navigator is now a global in nodejs` 也出现在本地扩展日志中，但同一轮依然完成了 SSH resolver 与 CLI 启动，暂未证实它是此次连接卡住的直接原因。

## 3. 本次采取的修复

### 3.1 使用用户自己的 SSH 公钥

用户将已有的个人公钥追加到树莓派授权列表后，Windows 到树莓派的免密 SSH 测试成功。这减少了 VS Code 重试时反复等待密码的问题，也便于直接验证远端安装状态。

私钥仍留在 Windows，公钥保存在树莓派的 `~/.ssh/authorized_keys`；没有把私钥写入文档或 Git 仓库。这是 Windows 登录树莓派的身份，与树莓派向 GitHub 推送代码使用的 GitHub 密钥是两套独立职责。

此前雷达配置任务使用过的临时维修密钥已经撤销；本次使用的是用户自己持有的密钥。

### 3.2 先备份 Windows VS Code 设置

原设置文件：

```text
C:\Users\huaima\AppData\Roaming\Code\User\settings.json
```

本次修改前的备份：

```text
C:\Users\huaima\AppData\Roaming\Code\User\settings.before-livox-remote-ssh-20261109-190134.json
```

保留原有其他设置，仅调整这次连接需要的项目。

### 3.3 改为 Windows 下载完整服务包

采用以下设置：

```jsonc
{
    // 固定使用已验证可用的 Windows OpenSSH，避免反复搜索其他程序目录。
    "remote.SSH.path": "C:\\Windows\\System32\\OpenSSH\\ssh.exe",

    // 明确此别名对应 Linux，不再重复询问平台。
    "remote.SSH.remotePlatform": {
        "raspberrypi-livox": "linux"
    },

    // 本次绕过 CLI / exec server 的中间层，采用直接服务安装路径。
    "remote.SSH.useExecServer": false,

    // 由 Windows 下载匹配版本的服务包，再通过 SSH 复制到树莓派。
    "remote.SSH.localServerDownload": "always"
}
```

上面是说明用的 JSONC 片段，不能覆盖整份已有设置。`useExecServer=false` 是本次采用的排查与绕行措施；不是已经证明“exec server 本身有缺陷”。`localServerDownload=always` 则用于避开树莓派直连下载中断的路径。

### 3.4 清理本次未完成下载占用的锁

第一次重试超时后，树莓派上留下了已确认属于本次 VS Code 安装的 `wget` 下载进程，它继续占用安装锁。后续日志反复出现获取锁提示。

本次只停止了已核实的下载进程 PID `13692`，让新的安装任务接管。没有使用 `killall wget`、关闭全部 SSH 连接或删除整个 `.vscode-server`。PID 是当时的现场值，不能作为以后可直接重跑的命令。

### 3.5 重新打开远程工作区

通过 `raspberrypi-livox` 重新打开 `/home/xin/livox_runtime`，由用户确认了工作区信任。

新日志的关键进展：

- `19:04:41`：出现 `Trigger local server download` 和 `Downloading VS Code server locally...`。
- `19:05:05`：Windows 完成下载，进入 `Preparing to scp to host raspberrypi-livox`。
- 随后服务包通过 Windows OpenSSH 的 `scp` 传向树莓派，日志显示持续增长的传输进度。
- `19:06:31`：服务包传输完成。
- `19:06:39`：解压成功，完整服务启动，SSH resolver 返回可用的连接地址。
- `19:07:00`：远程扩展主机恢复响应。

`scp` 预检查时不带文件参数，可能先输出用法并返回状态 1；这里后续已经执行真实复制并出现传输进度，因此不能把预检查的那一行单独判断为复制失败。

## 4. 最终验证结果

以下检查均已通过：

1. 完整服务包传输结束，安装日志显示 `unpackResult==success` 和 `didLocalDownload==1`，远端存在可执行的 `bin/code-server`。
2. VS Code 状态栏显示 `SSH: raspberrypi-livox`，不再显示“正在打开远程”。
3. 资源管理器列出 `config/`、`install/`、`env.sh`、`run_livox.sh` 等实际远端文件。
4. `run_livox.sh` 已在编辑器中打开并显示真实内容。
5. VS Code 的远程终端显示 `xin@ubuntu:~/livox_runtime$`；另通过普通 SSH 执行 `hostname`、`uname -m`、`pwd`，确认目标为 `ubuntu`、`aarch64`、用户家目录 `/home/xin`。
6. renderer 日志显示远程扩展主机由启动时的暂时无响应转为 `Extension host (Remote) is responsive`。

这些验证仅确认远程开发连接。它们不等同于重新验证雷达采集、FAST-LIO 建图或 SD 卡健康。远端中文语言包从扩展市场下载曾超时；这不妨碍本次已经完成的文件编辑和终端连接，也不需要因此重装雷达环境。

## 5. 回滚方法

本次主要修改 Windows VS Code 连接设置与安装其远程服务，不需要修改雷达运行脚本、JSON 或网口配置来处理本故障。

如果以后需要恢复修改前的设置，应先保存当前设置，避免丢失后续新增内容；再选择逐项恢复上述 `remote.SSH.*` 配置，或在确认没有其他新设置需要保留时恢复整份备份。

在 Windows PowerShell 中，完整恢复备份的示例：

```powershell
# 第一步：保留当前设置，备份名中加入时间，避免覆盖已有备份。
$settingsPath = "$env:APPDATA\Code\User\settings.json"
$currentBackup = "$env:APPDATA\Code\User\settings.before-rollback-$(Get-Date -Format yyyyMMdd-HHmmss).json"
Copy-Item -LiteralPath $settingsPath -Destination $currentBackup

# 第二步：仅在确认要完整恢复旧设置时执行这一条。
$originalBackup = "$env:APPDATA\Code\User\settings.before-livox-remote-ssh-20261109-190134.json"
Copy-Item -LiteralPath $originalBackup -Destination $settingsPath
```

恢复后重新加载 VS Code 窗口。这里的设置备份与树莓派文件备份不同，不包含密钥或完整远程服务安装包。

## 6. 后续遇到同类问题怎样判断

不要仅依据“正在初始化”这句界面文字确定故障阶段。依次确认：SSH 是否认证成功、CLI 是否启动、完整服务包是否下载和解压成功、管理与扩展连接是否建立、文件夹与远程终端是否真正可用。

记录日志时保留时间和错误正文，隐藏密码、私钥、访问令牌以及服务连接令牌。不要因为一次下载中断就清空整个运行目录或反复重装雷达驱动。
