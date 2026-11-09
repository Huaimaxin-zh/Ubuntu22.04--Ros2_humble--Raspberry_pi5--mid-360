# 把脚本和 Markdown 放到现有 GitHub 仓库

你的仓库：<https://github.com/Huaimaxin-zh/Ubuntu22.04--Ros2_humble--Raspberry_pi5--mid-360>。

## 1. Git、GitHub、Remote-SSH 各负责什么

| 工具 | 作用 |
| --- | --- |
| Git | 在当前机器记录文件版本、提交和分支 |
| GitHub | 保存推送上去的 Git 仓库，便于备份、查看和协作 |
| VS Code Remote-SSH | 从 Windows 编辑树莓派文件，远程执行 Git 和程序 |

Markdown `.md` 就是普通文本文件，和 `.sh`、`.py`、`.cpp` 一样通过 Git 提交。Git 不会自动记录尚未 `add` 和 `commit` 的修改。

建议主仓库中的资料统一放 `livox-mid360/` 子目录，不覆盖原 README 或其他项目。已有仓库应先 `clone`，保留原提交历史，不要重新 `git init` 后强推。

## 2. 首次从 Windows 整理并提交

此次本机已准备的源码资料目录：`C:\Users\huaima\livox-mid360-notes`。仓库检出目录：`C:\Users\huaima\livox-mid360-github`。如果本次任务已经建立了文档分支和提交，应先检查 `git status`、`git branch`，不用重复创建同名分支。

手动从头操作时，在 **Windows PowerShell** 执行：

```powershell
# 下载现有仓库；目录必须尚不存在，否则先查看已有检出目录。
git clone https://github.com/Huaimaxin-zh/Ubuntu22.04--Ros2_humble--Raspberry_pi5--mid-360.git C:\Users\huaima\livox-mid360-github

# 进入这个仓库，之后的 git 命令才针对它生效。
cd C:\Users\huaima\livox-mid360-github

# 查看当前分支和工作区状态。
git status

# 从现有历史建立资料分支，不直接修改 main。
git switch -c docs/livox-setup

# 将准备好的资料目录复制为仓库中的 livox-mid360 子目录。
# 仅在目标子目录尚不存在时执行，已有内容应逐文件合并。
Copy-Item -LiteralPath C:\Users\huaima\livox-mid360-notes -Destination .\livox-mid360 -Recurse
```

配置提交作者，仅针对当前仓库：

```powershell
# 请把姓名和邮箱改为你希望公开在提交记录里的身份。
git config user.name "Huaimaxin-zh"
git config user.email "你的GitHub提交邮箱"
```

GitHub“设置 → Emails”可找到用于保护真实邮箱的 `noreply` 地址。提交作者身份和登录 GitHub 的认证是两件事；不能只设置姓名邮箱就认为可以推送。

检查并提交：

```powershell
# 查看哪些文件新增、修改、未跟踪。
git status --short

# 仅添加本次资料目录；.gitignore 会过滤其中的备份、密钥和构建产物。
git add -- livox-mid360

# 查看即将提交的文件统计和具体差异。
git diff --cached --stat
git diff --cached

# 创建本地提交；此时还没有上传到 GitHub。
git commit -m "docs: 记录树莓派 MID360 配置和故障处理"

# 上传当前资料分支，首次通过浏览器或凭据管理器完成 GitHub 登录。
git push -u origin docs/livox-setup
```

Windows Git 已安装，HTTPS 推送通常会调用 Git Credential Manager。GitHub 不接受账号密码作为 Git HTTPS 密码；按弹出的浏览器登录流程操作，或使用自己的访问令牌。不要把令牌放在 remote URL、脚本或 Markdown 中。

推送成功后，在 GitHub 打开该分支，可以通过 **Compare & pull request** 创建合并请求，检查后再合并到 `main`。代码在分支上也已上传保存；尚未合并时查看 `main` 不会显示这些新文件。

## 3. 在树莓派克隆同一仓库

完成 Remote-SSH 后，在 **VS Code 的树莓派远程终端**执行：

```bash
# 查看 Git 是否可用。若原系统的 Git 损坏，应按实际错误处理。
git --version

# 为自己的项目建立目录，不在整个 home 或运行依赖目录做 git init。
mkdir -p ~/projects
cd ~/projects

# 建立树莓派自己的工作副本。
git clone https://github.com/Huaimaxin-zh/Ubuntu22.04--Ros2_humble--Raspberry_pi5--mid-360.git mid360-notes
cd mid360-notes

# 配置这份工作副本的作者身份。
git config user.name "Huaimaxin-zh"
git config user.email "你的GitHub提交邮箱"
```

如果资料分支还没合并到 main：

```bash
# 获取远程分支信息，再建立本地跟踪分支。
git fetch origin
git switch --track origin/docs/livox-setup
```

如果该分支已合并，保持 `main`，执行 `git pull --ff-only` 即可。随后在 VS Code 打开 `/home/xin/projects/mid360-notes`，左侧“源代码管理”就能看到文件变化。

## 4. 树莓派如何向 GitHub 推送

Windows 登录 GitHub 的凭据不会自动出现在树莓派。建议树莓派单独创建一对 **GitHub 专用密钥**：

```bash
# 在树莓派执行；同名文件已存在时不要覆盖。
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_github -C "raspberrypi-to-github"

# 显示的是 .pub 公钥，可复制到 GitHub；不要显示或上传无 .pub 的私钥。
cat ~/.ssh/id_ed25519_github.pub
```

在 GitHub 网页“Settings → SSH and GPG keys → New SSH key”粘贴该公钥。然后在**树莓派**的 `~/.ssh/config` 追加：

```sshconfig
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519_github
    IdentitiesOnly yes
```

设置权限并测试：

```bash
chmod 700 ~/.ssh
chmod 600 ~/.ssh/config
chmod 600 ~/.ssh/id_ed25519_github

# 首次连接核对 GitHub 官方发布的 SSH 主机指纹。
ssh -T git@github.com
```

成功提示通常是“successfully authenticated, but GitHub does not provide shell access”。这个测试可能返回非零退出码，以提示文字判断认证状态。

在该仓库中切换 remote 为 SSH：

```bash
cd ~/projects/mid360-notes
git remote set-url origin git@github.com:Huaimaxin-zh/Ubuntu22.04--Ros2_humble--Raspberry_pi5--mid-360.git
git remote -v
```

此时从树莓派 `git push` 使用树莓派上的 GitHub 专用密钥；Windows Remote-SSH 仍使用 Windows 上的树莓派登录密钥，两者独立。

## 5. 日常修改流程

```bash
# 先检查是否有未提交的修改。
git status

# 工作区干净且希望同步当前分支时，拉取远程提交。
git pull --ff-only

# 修改脚本和文档后，检查差异。
git diff

# 示例：只添加这次确实改过的文件。
git add -- livox-mid360/user-scripts/my_script.sh livox-mid360/docs/my-problem.md

# 提交描述写清楚做了什么。
git commit -m "fix: 记录重启后恢复雷达网口地址的方法"

# 推送当前分支。
git push
```

示例文件名需换成真实文件名。`git pull --ff-only` 被拒绝时先查看 `git status` 和 `git log --oneline --graph --all`，不要用强推或清空工作区解决。

VS Code 图形界面对应操作是：源代码管理中查看差异 → 点击文件旁的 `+` 暂存 → 写提交说明 → 提交 → 推送。GitHub 网页打开 `.md` 会自动渲染；VS Code 中可用 `Ctrl+Shift+V` 预览 Markdown。

## 6. 哪些内容不上传

源码、配置示例、少量验证 JSON 和 Markdown 适合 Git。完整 `livox_runtime`、`build/install/log`、SDK/ROS 安装库、点云数据、恢复压缩包和密钥应保留在 Git 之外。

仓库里的 `.gitignore` 已覆盖这些内容，但它只忽略尚未跟踪的文件，不能删除已有提交中的秘密。新增文件提交前仍需用 `git diff --cached` 查看内容。恢复包可继续放电脑或其他备份位置，无须为了记录流程把它提交进 Git 历史。
