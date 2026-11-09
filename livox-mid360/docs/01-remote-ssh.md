# 用 Windows VS Code Remote-SSH 操作树莓派

## 1. 先分清连接方向

Remote-SSH 让 Windows 上的 VS Code 打开树莓派文件，并在树莓派执行终端命令。它不要求树莓派安装桌面，也不需要先经过 VMware。

这里的 SSH 是 **Windows → 树莓派**。以后 `git push` 使用的是 **执行 Git 的机器 → GitHub**，两者的登录账号、密钥和认证过程分别配置。

## 2. 确认能用普通 SSH 登录

树莓派应已连接与 Windows 可互通的 Wi-Fi。先在树莓派已有终端查看：

```bash
# 在树莓派执行；wlan0 后面的 IPv4 地址是管理连接地址。
ip -br -4 addr show wlan0
```

本次地址为 `192.168.0.103`。如果现在输出不同，以下命令里的地址也要改。不要把雷达 `.20` 或树莓派雷达专用网口 `.123.4` 当作 Wi-Fi 管理地址。

在 **Windows PowerShell** 执行：

```powershell
# xin 是树莓派用户，@ 后面是树莓派 Wi-Fi 地址。
ssh xin@192.168.0.103
```

输入的是树莓派用户密码，终端输入密码时不会显示字符。首次连接需要核对主机指纹；可以在树莓派本地已有终端执行 `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub` 对照。

如果提示主机标识变化，先确认 IP 没有被分配给另一台设备，并核对指纹。确认确实是自己的树莓派后，才在 Windows 执行 `ssh-keygen -R 192.168.0.103` 删除对应旧记录，再重新连接；不要通过关闭指纹检查处理。

登录成功后输入 `exit` 返回 Windows。普通 SSH 还不通时先解决网络和账号问题，Remote-SSH 也无法绕过这些问题。

## 3. 配置自己的长期 SSH 密钥

此前维修任务的临时密钥已经删除和撤销，不能继续使用。这里生成你自己保管的新密钥。

在 **Windows PowerShell** 执行：

```powershell
# 创建 SSH 配置目录；目录已存在时保留原内容。
New-Item -ItemType Directory -Force "$env:USERPROFILE\.ssh" | Out-Null

# 创建一对专用密钥；如果同名文件已存在，停止并换文件名，不覆盖原密钥。
ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\id_ed25519_raspberrypi" -C "windows-to-raspberrypi"
```

生成过程中可以为私钥设置口令。两个文件用途如下：

| 文件 | 用途 |
| --- | --- |
| `id_ed25519_raspberrypi` | 私钥，保存在 Windows，本人保管，不复制到树莓派或 GitHub |
| `id_ed25519_raspberrypi.pub` | 公钥，可以追加到树莓派的授权列表 |

把公钥追加到树莓派：

```powershell
# 读取 .pub 公钥，并通过已有的密码 SSH 连接追加到 authorized_keys。
# >> 表示追加，保留树莓派已存在的其他授权。
# echo 先补一个换行，防止旧文件末尾没有换行时两条公钥粘在一起。
Get-Content "$env:USERPROFILE\.ssh\id_ed25519_raspberrypi.pub" |
    ssh xin@192.168.0.103 'umask 077; mkdir -p ~/.ssh; echo >> ~/.ssh/authorized_keys; cat >> ~/.ssh/authorized_keys; chmod 700 ~/.ssh; chmod 600 ~/.ssh/authorized_keys'
```

测试使用新密钥登录：

```powershell
ssh -i "$env:USERPROFILE\.ssh\id_ed25519_raspberrypi" xin@192.168.0.103
```

提示私钥口令时，输入刚才设置的口令。Windows OpenSSH 创建的私钥通常已有合适权限；若报 `UNPROTECTED PRIVATE KEY FILE`，检查文件属性中的安全权限，私钥不应由其他普通用户读取。

## 4. 配置连接别名

在 Windows 打开 SSH 配置：

```powershell
code "$env:USERPROFILE\.ssh\config"
```

将下面这一段追加进去，保留原来的其他连接配置：

```sshconfig
Host raspberrypi-livox
    HostName 192.168.0.103
    User xin
    Port 22
    IdentityFile ~/.ssh/id_ed25519_raspberrypi
    IdentitiesOnly yes
    ServerAliveInterval 30
    ServerAliveCountMax 3
```

`Host` 是你给连接起的别名；`HostName` 是真实地址。其他各项解释见 [带注释的示例](../examples/ssh_config.example)。保存后在 PowerShell 测试：

```powershell
ssh raspberrypi-livox
```

如果 Wi-Fi 地址变化，更新 `HostName`。也可以以后在路由器里为树莓派设置 DHCP 地址保留，避免每次查找地址；不需要更改雷达地址。

## 5. VS Code 连接

Windows VS Code 已在本次整理时安装 Microsoft 的 **Remote - SSH** 扩展。后续换电脑时，可在扩展页搜索安装，或运行：

```powershell
code --install-extension ms-vscode-remote.remote-ssh
```

操作顺序：

1. 按 `Ctrl+Shift+P` 打开命令面板。
2. 选择 `Remote-SSH: Connect to Host...`。
3. 选择 `raspberrypi-livox`，目标平台选择 **Linux**。
4. 按提示输入私钥口令或密码，等待安装 VS Code Server。
5. 左下角出现 `SSH: raspberrypi-livox` 后，使用“文件 → 打开文件夹”打开树莓派目录。

日常代码管理建议打开 Git 仓库，例如 `/home/xin/projects/mid360-notes`。查看已安装配置时可以打开 `/home/xin/livox_runtime`，但不要把整个运行依赖目录初始化成 Git 仓库。

在远程 VS Code 的“终端 → 新建终端”中执行：

```bash
# 确认命令执行位置确实是树莓派。
hostname
uname -m
pwd
```

`uname -m` 应为 `aarch64`。这个终端里执行的 Git、Python、CMake 和驱动程序都在树莓派运行，不消耗虚拟机的编译环境。

## 6. 常见连接问题

| 现象 | 排查方向 |
| --- | --- |
| 超时 / No route to host | 树莓派 Wi-Fi 地址变了、设备不在线或网络无法互通 |
| Permission denied | 用户名、公钥追加、私钥路径或文件权限不正确 |
| VS Code Server 下载失败 | 树莓派或电脑访问下载站点受限；查看“输出 → Remote - SSH”的具体失败项 |
| 端口转发被禁止 | 查看 SSH 服务设置是否限制 TCP 转发，不要无依据修改整份 sshd 配置 |
| VS Code Server / Git 报文件异常 | 原系统已有文件损坏可能影响其他程序；本次独立 ROS 环境不保证修复了系统所有工具 |

先在本机 PowerShell 运行 `ssh -v raspberrypi-livox` 获取连接诊断，再按具体错误处理。不要把密码、私钥或访问令牌写进问题记录。

本次还遇到了 CLI 已启动、完整 VS Code Server 下载却在约 33% 中断的情况。改由 Windows 下载并通过 SSH 传输后连接成功；具体证据、设置备份和回滚方法见 [Remote-SSH 初始化故障记录](06-remote-ssh-troubleshooting.md)。
