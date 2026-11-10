# 驱动源码修改记录

## 新卡 SDK 符号绑定补丁（2026-11-10）

[`sdk-spdlog-symbol-binding.patch`](sdk-spdlog-symbol-binding.patch) 基于官方 Livox-SDK2 提交 `c0796f04c143143899c87a773d9f6b7136453c0b`。它只在 Linux 平台为 SDK 共享库目标增加 `-Wl,-Bsymbolic`，把共享库内部的符号引用绑定到自身实现，避免 SDK 内嵌 spdlog 1.3.1 与 ROS2 系统 spdlog 1.9.2 的同名 C++ 符号混用。

故障是采集正常、单次 SIGINT 退出时驱动段错误。与正式 Launch 等价的 gdb 复现显示：SDK 中 `std::shared_ptr<spdlog::logger>` 析构进入系统 `libspdlog.so.1`，随后 SIGSEGV。修复后的 SDK 动态段有 `SYMBOLIC`，修复前后 1574 个动态导出符号名称一致，`ldd -r` 无未解析符号。没有修改 ROS2 系统库。完整实测见 [真实验收记录](../docs/11-mid360-fastlio-live-acceptance.md)。

| 留档对象 | SHA256 |
| --- | --- |
| `sdk-spdlog-symbol-binding.patch` | `663a32a45aa5d067d503a1e9bc5e6e176b0d28951dc3fb7e0d47a980ef8d9737` |
| 修改后的 SDK `sdk_core/CMakeLists.txt` | `10244ef009035975fa391a015a72634f3eba768fe13b8b02829967529dba1066` |
| 本卡修复后的 SDK 共享库 | `2afc324484893ea44e63ded891709bdba5ce5501e80f89c2ae8e6e235a3636b7` |

已在锁定上游源码验证 `git apply --check`。[`build_sdk2.sh`](../scripts/stack/build_sdk2.sh) 现在先核对上游提交和补丁 SHA256，再检查是否已应用；已应用则跳过，未应用且正向检查通过才应用，冲突时停止，避免重新构建出未修复的 SDK。复现前先把补丁复制到树莓派 `~/livox_stack_setup/patches/`，详见验收记录。

本卡 SDK 为“官方基础提交 + 本地符号绑定补丁”；驱动源码已经恢复到官方基础提交，仅配置改变。此前前置 PubHandler 退出顺序的候选修改没有解决故障，已撤回，不在正式补丁中发布。不要把本补丁和下述旧卡恢复补丁盲目混用。

## 旧卡恢复期间的历史补丁

`livox-driver-session.patch` 来自本次恢复前工作区与最终工作副本之间的差异，记录移除未使用 APR 依赖、退出线程唤醒和原子退出标志等调整。

它**不是完整的官方源码到最终版本的差异**：去除 ROS2 路径未使用 PCL 依赖的调整在本次接管前已经存在。因此，不应假定向任意官方版本应用这一份补丁就能得到完整最终源码。

上游版本记录见 `../upstream-versions.json`。需要向驱动本身提交修改时，应在对应上游仓库或自己的 fork 中管理源码、保留原许可和提交历史。本资料仓库以操作记录和自编工具为主。
