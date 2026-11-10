# SD 卡维修指令留档：识别、备份、副本修复与原卡验收

日期：2026-11-10（北京时间）。这是本次已经执行过的指令及结果记录，**不是可以从头直接运行的自动修复脚本**。磁盘路径和镜像目录均属于本次现场，重新插拔设备后必须重新识别。

**最终结果：原卡未修复；整卡备份完整，包含文件数据的根分区副本修复通过，已生成尚未实机启动验证的恢复候选镜像。** 完整分析见 [维修报告](07-sd-card-recovery-report.md)。

精简的实际结果和校验值见 [验收证据 JSON](../evidence/2026-11-10-sd-card-recovery.json)。下列命令保留实际选项与目标，并补充中文注释；控制程序原本以root执行的命令，人工入口补写了`sudo`。

## 1. 第一条指令：先识别磁盘

```bash
# 只读：列出磁盘大小、USB连接类型、文件系统和挂载点，隐藏无关loop设备。
# 不修改分区，也不会修复文件系统。
lsblk -e 7 -o NAME,PATH,SIZE,MODEL,TRAN,RO,FSTYPE,LABEL,MOUNTPOINTS
```

本次识别结果：

| 本次设备 | 容量及特征 | 如何处理 |
| --- | --- | --- |
| `/dev/sda`、`/dev/sda3` | 40GiB VMware虚拟硬盘，`sda3`挂载为`/` | 虚拟机系统盘，不是维修目标，禁止对其运行本次修复 |
| `/dev/sdb` | 29.1GiB USB读卡器中的SD卡 | 本次整卡只读备份来源 |
| `/dev/sdb1` | 512MiB vfat，标签`system-boot` | 引导分区 |
| `/dev/sdb2` | 28.6GiB ext4，标签`writable` | 本次待修复根分区 |

不能仅凭字母`b`判断是SD卡。实际同时核对USB类型、容量、标签、UUID和分区几何信息。本次根分区UUID为`b171cb0e-a208-4406-9f96-31741fd34cdb`。重新连接后，`sdb`可能变成其他名字。

```bash
# 只读：直接探测这次已识别根分区的UUID，避免依赖旧的blkid缓存。
sudo blkid -p -s UUID -o value /dev/sdb2

# 只读：查看虚拟机主目录所在磁盘的剩余空间。
# 本次只剩约12GiB，装不下约29.1GiB整卡镜像，必须另找备份目标。
df -h "$HOME"
```

## 2. 卸载后检查，避免在线修复

```bash
# 正常卸载SD卡引导分区；不会删除文件。
# 若提示busy，先查明占用原因，不强制卸载，不在仍挂载时修复。
sudo umount /dev/sdb1

# 正常卸载SD卡根分区，风险和前一条相同。
sudo umount /dev/sdb2

# 只读核对：两个分区的MOUNTPOINTS应为空。
lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINTS /dev/sdb

# 只读完整检查：-f强制检查，-n以只读方式打开并拒绝修复，-v显示详细统计。
# 这一步发现位图、计数和校验和不一致；没有修复原卡。
sudo e2fsck -f -n -v /dev/sdb2
```

`e2fsck`提示的`0 bad blocks`不是本次做过完整坏块扫描的证明。`RO=0`只说明块设备没有只读标志，不能证明写入可靠。内核中`dev fd0`的I/O错误属于虚拟软驱，不能归到SD卡。

## 3. 先保全 home 和 etc

以下是本次为复制文件而采用的只读挂载方式。`noload`阻止挂载时回放ext4日志，因此读取到的目录视图可能仍包含故障时的不一致；它适合抢救文件，不能当作一致性修复。

```bash
# 只在虚拟机系统盘创建空挂载目录，不写SD卡。
sudo mkdir -p /mnt/pi-sd-recovery

# 以只读且不回放日志方式挂载本次SD根分区。
# 必须先确认它确实是本次卡；挂载期间不运行e2fsck修复。
sudo mount -o ro,noload /dev/sdb2 /mnt/pi-sd-recovery

# 定义带时间的新备份文件名；不会修改SD卡。
# 此变量属于当前shell，换终端后不能假定仍存在。
pi_backup="$HOME/pi-home-etc-before-fsck-$(date +%Y%m%d-%H%M%S).tar.gz"

# 从SD卡读取home、etc，压缩备份写入虚拟机主目录。
# 保留ACL、扩展属性和数字所有者；它不是整卡备份。
sudo tar --acls --xattrs --numeric-owner --sparse \
  -czpf "$pi_backup" -C /mnt/pi-sd-recovery home etc

# 必须紧接上条执行，防止读到其他命令的退出码；本次输出0。
echo "备份退出码：$?"

# 只读校验压缩流；成功通常不输出文字，本次退出0。
sudo gzip -t "$pi_backup"
echo "压缩校验退出码：$?"

# 只读显示备份大小；本次约71MiB。
sudo ls -lh "$pi_backup"

# 正常卸载；后续修复前再次用lsblk确认挂载点为空。
sudo umount /mnt/pi-sd-recovery
```

本次压缩文件名为`pi-home-etc-before-fsck-20261110-002750.tar.gz`，保存在虚拟机用户主目录。仓库不上传这个包含用户文件和配置的压缩包。

## 4. VMware 共享备份目录

Windows端在VMware中启用名为`pi-sd-recovery`的共享目录，对应本机用户目录下的`pi-sd-recovery`文件夹。以下命令在Ubuntu虚拟机中执行。

```bash
# 只读查询VMware发布的共享名称，不修改SD卡。
vmware-hgfsclient

# 只在虚拟机创建共享目录的挂载点。
sudo mkdir -p /mnt/pi-host-backup

# 挂载Windows共享；写入目标是Windows目录，不是SD卡。
# allow_other允许其他本地用户访问该挂载，适用于本次受控单用户维修环境。
sudo vmhgfs-fuse .host:/pi-sd-recovery /mnt/pi-host-backup -o allow_other

# 只读核对实际挂载来源及类型；必须确实命中HGFS，不能只看到空目录。
findmnt /mnt/pi-host-backup

# 只读核对备份空间；本次成功连接后显示约271GiB可用。
df -h /mnt/pi-host-backup
```

最初出现`Error -107 cannot open connection!`，`df`仍显示虚拟机`/dev/sda3`，因此没有把该目录当作可用备份目标。修正VMware共享设置后才挂载成功。后来HGFS目录枚举又出现EIO，重新挂载并采用隔离的Python导入路径：

```bash
# 以下三条是修复共享连接后实际执行的启动顺序；&&让失败时停止后续步骤。
# 卸载对象是Windows共享，不是SD卡分区；共享正在被使用时不得盲目重挂。
sudo umount /mnt/pi-host-backup &&
sudo vmhgfs-fuse .host:/pi-sd-recovery /mnt/pi-host-backup -o allow_other &&
sudo python3 -I -S /mnt/pi-host-backup/sd_repair_control.py
```

最后一条启动本次人工审查过的临时root控制程序。`-I -S`隔离导入路径并跳过site初始化，不是“修复Python”的命令。程序只接受白名单动作，不能任意执行shell；原卡写入修复需要完整备份、副本通过只读检查、实时身份一致且未挂载。启动root会话有权限风险，不能对来源不明的脚本使用这条命令。

开始大备份前，程序在共享目录创建、同步、改名、重读16MiB测试文件，并由Windows独立重读核对SHA256，双方一致。只做目录存在性检查不足以证明共享可靠。

## 5. 完整原始备份与双侧校验

下面是控制程序实际调用的命令，人工从普通终端执行时需要相应权限。**ddrescue第一个路径是输入，第二个路径是输出，第三个路径是map；本次输出只允许全新普通文件，不能交换顺序。**

```bash
# 在虚拟机安装GNU ddrescue；修改虚拟机软件包，不写SD卡。
# 本次安装版本为gddrescue 1.23-2build1。
sudo apt-get install -y gddrescue

# 本次整卡只读来源是已确认的/dev/sdb。
# -n跳过scraping阶段；--结束选项；写出的仅是Windows共享中的新镜像和map。
# 运行前已确认两个分区卸载、目标空间足够，并禁止覆盖既有备份目录。
sudo ddrescue -n -- /dev/sdb \
  /mnt/pi-host-backup/pi-original-backup01/sdcard-original.img \
  /mnt/pi-host-backup/pi-original-backup01/sdcard-original.map

# 完整读取备份普通文件计算SHA256，不修改原始镜像。
sha256sum /mnt/pi-host-backup/pi-original-backup01/sdcard-original.img
```

Windows端独立读取同一文件：

```powershell
# 只读计算Windows普通镜像文件SHA256；不访问原始磁盘。
Get-FileHash -LiteralPath "$env:USERPROFILE\pi-sd-recovery\pi-original-backup01\sdcard-original.img" -Algorithm SHA256
```

本次从01:35:08备份到04:27:25，最终退出0、零读取错误；镜像长度精确为`31266439168`字节。map从0连续覆盖全卡且全部为`+`，`source.json`的`complete=true`。仅ddrescue退出0不足以代替这几项验收。

双侧完整SHA256一致：

```text
b5db0dc24a2b9e15ac64a6e18e30a423055084363d9bf58bf3cf14a5b7e42dda
```

## 6. 元数据测试和完整根分区副本不是一回事

早期先制作了包含journal的稀疏元数据镜像，在其测试副本上运行`e2fsck`后复查退出0。该类镜像不包含普通文件的完整内容，**不能回写原卡，也不能作为系统恢复镜像**。这次没有把元数据镜像写回任何磁盘。

整卡备份完成后，实际采用Windows普通文件脚本提取完整根分区：

```powershell
# 本次使用H盘已有Python；该安装路径只是现场工具路径，不是所有电脑的默认值。
# -S跳过site初始化；脚本仅以只读方式打开原始整卡镜像。
# 写入新rootfs-work.img，并在关闭写入句柄后完整重读比对SHA256。
& 'H:/python/python.exe' -X utf8 -S "$env:USERPROFILE/pi-sd-recovery/extract_root_copy_host.py"
```

该脚本有固定现场路径和几何约束，校验`source.json`与全盘map，拒绝覆盖既有输出。它是本次本地工具，本文只记录实际入口，脚本源码未随本文发布；克隆仓库后该文件不会自动出现在用户主目录。临时控制程序虽然也有`copy_root`动作，但本次**没有执行它的ddrescue提取命令**，不把未执行的路径记为实绩。

实际根分区输入偏移为`537919488`，提取长度为`30728502784`字节；包含普通文件数据。修复前输入区段和输出完整重读SHA256均为`495e723c6330b7e5cc766d46146095d3e3af05c545fe7b899e1d1380689ae594`。

## 7. 完整副本修复和原卡修复的不同结果

控制程序以root执行以下命令；命令中的`.img`是Windows共享上的普通文件，不能替换成原始整卡镜像。

```bash
# 会修改rootfs-work.img的文件系统元数据；原始整卡镜像保持只读保留。
# -f强制检查，-v显示细节；不使用-y，以便逐项审查提示。
sudo e2fsck -f -v /mnt/pi-host-backup/pi-original-backup01/rootfs-work.img

# 只读复查完整副本；必须看到五个检查阶段并退出0，本次达到该条件。
sudo e2fsck -f -n -v /mnt/pi-host-backup/pi-original-backup01/rootfs-work.img

# 只读查看超级块及journal摘要，作为辅助证据，不能替代完整检查。
sudo dumpe2fs -h /mnt/pi-host-backup/pi-original-backup01/rootfs-work.img
```

本次副本日志恢复成功，后续提示是块位图和空闲计数不一致，逐项选择`y`修正；修复退出1表示已修正，随后完整只读复查退出0。`dumpe2fs`显示`needs_recovery`消失、`Journal start: 0`。

遇到`Run journal anyway<y>?`时，本次针对已备份且未挂载的目标选择`y`回放日志。对涉及大量清除inode、重建journal等不同提示，不能套用本次结论，更不能把所有问题自动回答yes；应停止并先分析。

原卡写入前重新核对UUID、USB类型、容量、分区几何、RO=0和无挂载，并记录主超级块、journal块的摘要。随后实际执行：

```bash
# 这是本次历史写入尝试，会修改SD卡元数据。
# 只有完整备份和完整副本检查通过后才执行；当前卡已失败，不建议重复照抄。
sudo e2fsck -f -v /dev/sdb2

# 修复后只读完整复查，不继续写卡。
sudo e2fsck -f -n -v /dev/sdb2

# 只读读取原卡的超级块摘要。
sudo dumpe2fs -h /dev/sdb2

# 只读检查FAT引导分区；-n保证不保存修正。
sudo fsck.fat -n -v /dev/sdb1
```

结果对比：

| 目标与步骤 | 退出码 | 实际含义 |
| --- | --- | --- |
| 完整根副本交互修复 | 1 | 检出并修正错误 |
| 完整根副本五阶段只读复查 | 0 | 结构检查通过 |
| 原卡交互修复 | 12 | 仍有未修复错误和操作错误 |
| 原卡只读复查 | 4 | 仍有未修复错误 |
| 引导分区`fsck.fat -n` | 1 | dirty bit仍在，输出`Leaving filesystem unchanged`，未修改 |

原卡再次输出`unable to set superblock flags on writable`，journal start仍为`11129`。修复前后主超级块和journal超级块SHA256完全相同，预期更新未保留，因此停止重复写入。该报错不是直接的底层写入errno，不能单凭一句错误断言硬件彻底损坏。

### 树莓派 initramfs 中的早期尝试

在树莓派进入initramfs时，先用`mount`确认`/dev/mmcblk0p2`未挂载为根目录，再尝试：

```bash
# 只读列出内核识别的分区，区分设备未识别和文件系统错误。
cat /proc/partitions

# 只读查看设备节点；本次确认mmcblk0p2确实存在。
ls -l /dev/mmcblk*

# 本次历史修复尝试；会写卡，不在仍挂载的分区上运行。
fsck.ext4 -f -v /dev/mmcblk0p2
```

早期一轮曾提示设备不存在，随后重新核对分区和设备节点。设备可见后选择`yes`回放日志，仍出现同样的超级块标志错误。因此后续转移到虚拟机离线备份及修复，没有把Pi端尝试算作成功。

## 8. 恢复候选镜像与安全结束

```powershell
# 仅在Windows普通文件之间组装恢复候选；原始整卡镜像和根副本均以只读方式打开。
# 新建sdcard-recovered.img，替换其中根分区区段，再完整重读三段SHA256。
# 这条命令没有向任何原始磁盘写入。
& 'H:/python/python.exe' -X utf8 -S "$env:USERPROFILE/pi-sd-recovery/assemble_recovered_disk_host.py"
```

最终候选长度为`31266439168`字节，完整重读SHA256为`a528bc20e1fcc862729582fad39b94cf641fc56898b9f92d882e3933c3bcc330`。引导分区原样保留，包括dirty bit；尚未在新卡启动，之前损坏的软件文件内容也不会因fsck自动恢复。

```bash
# 本次两个分区均卸载后，向已确认整卡发送安全断电请求。
# 它会让读卡器中的卡离线；本次退出0，之后才可以取卡。
sudo udisksctl power-off -b /dev/sdb
```

最后通过控制客户端提交白名单`stop`动作，临时维修程序最终状态为`stopped`，没有遗留root维修任务。本次没有格式化、清空分区、重分区，也没有把镜像覆盖写回原卡。

GNOME自动挂载此前为避免意外挂载而暂时关闭；旧设置保存在虚拟机用户目录`pi-sd-diagnostic-*/automount-before.txt`，本次没有恢复该设置。日后恢复前应读取原值，不能假设原值一定为true。

## 9. 指令与发布范围

本次运行的控制程序版本SHA256前缀为`d47b0e0b`，与后续本地修订源码`39b204c0`不同。对运行版本采用了只允许首次共享探测并独立校验的受限兼容路径；没有在运行中替换其代码，也没有复用失败后的旧共享确认。

GitHub仅公开可读记录、指令和经整理的结果；本次临时控制及镜像处理脚本源码未随本文发布。不上传控制会话token、root会话状态文件、请求/回复原文、SSH密钥、VMX现场配置、用户文件压缩包、整卡镜像或恢复候选镜像。本文中的本地脚本名称用于解释实际执行机制，不是通用一键修复入口。

可以用于成功判断的是：目标分区卸载、完整检查退出0、断开重连后再次通过，最后实机启动和应用验证。本次只有完整副本通过结构验收，原卡没有达到成功条件。
