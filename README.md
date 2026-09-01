# Clash SubScope · 订阅透镜

> 🔍 **一键提取本机 Clash 客户端的订阅链接** —— 仅读本地、默认脱敏、零上传。

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform: Windows](https://img.shields.io/badge/platform-Windows-0078d4.svg)]()
[![Python: 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)]()
[![Status: Read-Only / Privacy-First](https://img.shields.io/badge/status-read--only-success.svg)]()
[![Release: v1.2.8](https://img.shields.io/github/v/release/cv-superding/clash-subscope?label=release&color=0078d4)]()

> 🔍 **One-click extract subscription links from your local Clash clients** —
> read-only · masked by default · zero upload.

---

## 📑 目录

- [🤔 为什么做这个](#-为什么做这个)
- [✨ 特性一览](#-特性一览)
- [📸 截图](#-截图)
- [📥 下载（免 Python 环境）](#-下载免-python-环境)
- [🔒 隐私与安全（请务必先读这一节）](#-隐私与安全请务必先读这一节)
- [📦 安装](#-安装)
- [🚀 基础使用](#-基础使用)
- [🎯 核心功能：导入订阅到 Clash](#-核心功能导入订阅到-clash)
- [🔐 关于管理员权限与 Clash 服务](#-关于管理员权限与-clash-服务)
- [🔍 支持的客户端](#-支持的客户端)
- [🔧 工作原理](#-工作原理)
- [🩺 常见问题与排查](#-常见问题与排查)
- [📁 项目结构](#-项目结构)
- [📝 更新日志](#-更新日志)
- [🤝 致谢](#-致谢)
- [📄 许可证](#-许可证)

---

## 🤔 为什么做这个

Clash 系客户端（包括 Clash Verge Rev / Clash for Windows / FlClash / Nyanpasu /
独立 mihomo 核心）的订阅地址都保存在本机配置文件里，但它们不给你任何"复制订
阅链接"的可点击按钮，只能从 `%APPDATA%` 下的 YAML 文件里翻找。

当你想：

- 在另一台设备上用同一个订阅
- 把订阅迁移到另一个客户端
- 备份当前正在用的订阅
- 排查某个订阅有没有过期
- 写一个属于你自己的订阅管理脚本

……的时候，本工具就是为此存在的。

---

## ✨ 特性一览

| 功能 | 描述 |
| --- | --- |
| 🖱️ **一键扫描** | GUI 单按钮，自动找出本机已安装的所有 Clash 客户端 |
| 📋 **完整订阅列表** | 按配置名称逐一列出，每条都给出客户端、来源、更新/流量/到期 |
| 🎯 **当前配置高亮** | 运行时能拿到核心当前生效配置，会在表格里加"使用中"标记 |
| 🔄 **多客户端并存** | 同台机器装多个 Clash（Verge + FlClash + CFW 等）都识别 |
| 🔁 **重复链接提示** | 同一个 URL 被多个配置引用时，状态列显示「共用×N」 |
| 🕶️ **默认脱敏** | 链接前 30 字符 + 中段打码 + 末尾 4 字符；可一键切换明文 |
| 📎 **一键复制** | 单条 / 全部，复制到剪贴板 |
| 💾 **导出 TXT** | 完整可读文本，含每条配置的全部信息 |
| ➕ **一键导入到 Clash** | 粘贴订阅链接 → 自动关 Clash（连服务一起）→ 关系统代理 → 写入 `profiles.yaml` → 引导你更新与恢复 |
| 🔧 **运行时探测** | 同时支持 TCP（`external-controller`）与 Windows 命名管道，核心关闭 TCP 时自动回落管道 |
| 🔒 **写前自动备份** | 导入前备份 `profiles.yaml`（带时间戳 + 随机后缀），失败自动回滚 |
| 🌐 **全中文界面** | 现代化浅色主题（ttkbootstrap / cosmo），统一圆角按钮与原生风格滚动条，无任何依赖外网的服务 |

---

## 📸 截图

![GUI 总览](docs/screenshot.png)

*Clash Verge Rev 下的订阅配置列表：当前正在使用的配置用浅蓝高亮，
同一链接被多个配置共用时在状态列显示「共用×N」。底部诊断区为空表示一切正常。*

---

## 📥 下载（免 Python 环境）

不想装 Python / 依赖？直接去 Releases 下载打包好的单文件 exe：

- 👉 [clash-subscope.exe（v1.2.8）](https://github.com/cv-superding/clash-subscope/releases/download/v1.2.8/clash-subscope.exe)

双击即可运行（Windows 10 / 11）。同样遵循「仅读本地、默认脱敏、零上传」的隐私承诺。

> 💡 **准备使用「导入订阅」功能？** 建议**右键 exe → 以管理员身份运行**。
> 原因见 [关于管理员权限与 Clash 服务](#-关于管理员权限与-clash-服务)。
> 只做查看 / 复制 / 导出则无需管理员。

---

## 🔒 隐私与安全（请务必先读这一节）

**这是这个项目最在意的一条承诺：如果你的环境不允许，把工具扔掉也无所谓，但
这几点不能含糊：**

1. **不访问任何外网。**
   运行时接口（用于读取核心版本 / 节点数）只连 `127.0.0.1` 或本机命名管道。
   它绝不会对你列出的订阅链接发起任何请求。

2. **不上传任何数据。**
   工具全程没有"埋点"、没有"数据回传"、没有"配置文件同步"。复制 / 导出按
   用户在 UI 上的按钮触发，确认后写入本地文件，不与任何服务端通信。

3. **不尝试破解加密的客户端配置。**
   部分 Clash for Windows 0.20+ 会把 `profiles.yml` 加密存储。工具会明确提示
   "疑似已加密或已损坏"，并指引用户在客户端内关闭加密，但**绝不调用任何解密
   函数、绝不绕过认证**。

4. **默认打码显示订阅链接。**
   中段打码，仅保留前 30 / 末尾 4 字符。即使有人在你旁边也不容易窥到完整链接。
   想要明文时手动勾选"显示完整链接"。

5. **唯一的写操作有备份与回滚。**
   工具只有"导入订阅"这一个写操作，且在写入前会备份原 `profiles.yaml`
   （文件名含时间戳 + 随机后缀），写入失败自动回滚，绝不破坏原配置。

6. **完全离线运行。**
   工具本体不需要安装包以外的任何下载；只需 Python + 三个依赖
   （见下方[依赖](#依赖)）。装完之后离线启动零网络请求。

> 如果你愿意审计源码：所有读写路径都在 `clash_sub_tool/` 下，搜索关键字
> `urlopen` / `http.client` / `requests` 都搜不到（不是没找到，是真的没有）。

---

## 📦 安装

### 方式 1：直接下载 exe（最省事）

见上方[下载](#-下载免-python-环境)，双击即用，无需安装 Python。

### 方式 2：双击启动器（源码用户推荐）

仓库自带 `clash-subscope.bat`：

```bat
:: 双击即可
clash-subscope.bat
```

启动器默认指向 `C:\Users\29436\anaconda3\pythonw.exe`。**如果你的 Python
不在这个路径**，用任意编辑器打开 `.bat`，把 `PYTHONW`（和 `PYTHON`）改成你自己
的 `pythonw.exe` / `python.exe` 路径，再保存后双击。

启动器会自动检查并安装缺失的 PyYAML。

### 方式 3：手动启动

```bat
:: 安装依赖
pip install -r requirements.txt

:: GUI 需要 pythonw（不是 python），避免弹出黑色控制台窗口
pythonw main.py
```

### 依赖

```
PyYAML >= 6.0        解析 profiles.yaml / profiles.yml / config.yaml
psutil >= 5.9        枚举本机进程，识别 Clash 主程序 / 服务是否运行
ttkbootstrap >= 2.2.2  现代化 UI 主题（cosmo），替代原生 tkinter 控件样式
```

Python 3.8+。Windows 10 / 11 实测通过。

> ⚠️ **打包提示**：若你自行用 PyInstaller 打包，**不要**加 `--exclude-module PIL`
> —— ttkbootstrap 内部依赖 `PIL.ImageColor`，排除后 exe 启动会崩溃。

---

## 🚀 基础使用

1. 启动后 GUI **自动扫描一次**，无需手动触发。
2. **状态卡片**告诉你 Clash 客户端的运行情况、核心版本、控制器通道。
3. **订阅表格**列出所有订阅配置。
4. 想要某一条链接 → 选中 → 「复制选中链接」。
5. 想要全部 → 「复制全部链接」。
6. 想存档 → 「导出为 TXT」。
7. 需要明文 → 勾选「显示完整链接（关闭脱敏）」，导出同理。
8. 选一行后切到「选中项详情」tab 看完整 metadata。
9. 想刷新 → 点「一键扫描」。

---

## 🎯 核心功能：导入订阅到 Clash

这是本工具**唯一的写操作**，也是唯一需要额外注意权限的功能。它解决的是一个很
常见的痛点：

> 朋友发你一条订阅链接，你在 Clash 里点"导入"却失败——
> 报 `http2 error` 或 403，因为**系统代理（梯子）把拉取请求绕去了出口 IP，
> 被订阅服务端中断或拦截**。

工具的做法：**关掉代理 → 让 Clash 直连拉取 → 写完再让你恢复代理**。

### 完整流程（逐步）

**第 1 步 · 粘贴链接**

在顶部「导入订阅到 Clash」输入框粘贴链接，或从表格选中一行后点「导入选中到 Clash」。

**第 2 步 · 确认**

弹出确认框，告诉你接下来会发生什么，点「确认」继续。

**第 3 步 · 关闭 Clash（如正在运行）**

若检测到 Clash 正在运行，工具会**再问一次**是否允许关闭。点「是」后，工具会：

- 终止 Clash 主程序（`clash-verge.exe` / `verge-mihomo.exe` 等）
- **同时终止其 Windows 服务**（`clash-verge-service.exe`）
  —— 关键！否则服务会毫秒级把主程序拉回来
- 按 pid 逐个探测，等待进程**真正退出**后才继续（最多等 3 秒）

**第 4 步 · 临时关闭系统代理**

保存你当前的系统代理设置，然后把 `ProxyEnable` 置 0。右上角「恢复代理」按钮
此时会亮起可用。

**第 5 步 · 备份并写入**

- 备份原 `profiles.yaml` → `profiles.yaml.bak_import_<时间戳>`
- 追加一条 `type: remote` 订阅条目
- 若链接已存在则**跳过**（不重复添加）
- 写入失败自动回滚，并恢复系统代理

**第 6 步 · 你手动完成剩下的事**

工具**不会**替你拉节点。请按弹窗提示：

1. 重新打开 Clash
2. 选中新订阅，点「更新」（此时代理已关，可直连拉取、避开 HTTP/2 / 403）
3. 节点拉取完成后，点本工具右上角「恢复代理」重新开梯子

> ⚠️ **导入成功后直接关掉工具窗口？** 会弹窗问你是否立即恢复代理——
> 选「否」可保持代理关闭（方便你先去点更新），选「是」则恢复后退出。

---

## 🔐 关于管理员权限与 Clash 服务

### 为什么需要管理员？

Clash Verge Rev 等客户端会安装一个 **Windows 服务**（`clash-verge-service.exe`），
它的职责是**"主程序死了就立刻拉起"**。这是个有用的设计，但对"导入配置"是致命的：

| 进程 | 类型 | 谁启动 | 何时停止 |
| --- | --- | --- | --- |
| `clash-verge.exe` | 普通 GUI 进程 | 你点桌面图标 | 托盘退出 / 被工具终止 |
| `verge-mihomo.exe` | 普通核心进程 | GUI 拉起 | 跟随 GUI 退出 |
| **`clash-verge-service.exe`** | **Windows 服务** | **开机自启动** | **重启系统 / 手动禁用** |

也就是说：**即使你"关掉"了 Clash 窗口，服务仍在后台运行**，且它会把你刚 kill 掉的
主程序立刻拉回来，导致写入的 `profiles.yaml` 被新进程覆盖——这就是"导入看起来成功
但配置没生效"的根因。

而**终止 Windows 服务需要管理员权限**。所以：

### ✅ 推荐做法

**右键 `clash-subscope.exe` → 「以管理员身份运行」**，然后再点导入。

工具在检测到服务且终止失败时，会明确弹出提示告诉你这一点，不会静默失败。

### 🔧 可选：一劳永逸地禁用服务

如果你不希望每次都提权，可以在服务管理器里禁用它：

1. `Win + R` → 输入 `services.msc` → 回车
2. 找到 `Clash Verge Rev Service`（或名称含 "service" 的同名服务）
3. 右键 → **属性** → **启动类型**改为「禁用」
4. 右键 → **停止**

之后工具只需终止两个普通进程，不再需要管理员权限。

> **副作用**：Clash 主程序崩溃后不会自动重启。对日常使用几乎无影响。

### 只做查看 / 复制 / 导出需要管理员吗？

**不需要。** 查看订阅、复制链接、导出 TXT 都是纯读取操作，普通权限完全够用。
只有"导入订阅"这个功能会碰服务。

---

## 🔍 支持的客户端

| 客户端 | 配置文件 | 数据目录（默认） |
| --- | --- | --- |
| **Clash Verge Rev** | `profiles.yaml` | `%APPDATA%\io.github.clash-verge-rev.clash-verge-rev` |
| Clash Verge（旧版） | `profiles.yaml` | `%APPDATA%\io.github.clash-verge.clash-verge` 等 |
| Clash Nyanpasu | `profiles.yaml` | `%APPDATA%\top.gydong.clash.nyanpasu` |
| FlClash | `profiles.yaml` | `%APPDATA%\com.follow.clash` 等 |
| Clash for Windows | `profiles.yml` | `%APPDATA%\Clash for Windows` |
| Mihomo / Clash.Meta（独立核心） | `config.yaml` | `%USERPROFILE%\.config\clash` 等 |

如果客户端用了自定义数据目录（绿色版），只要位于上述常见路径下即可被自动
找到。要加新客户端只需在 `clash_sub_tool/clients.py` 的 `CLIENT_DEFS` 加一
项，通常 `flavor="verge"` 就能复用现有解析逻辑。

### 运行时接口通道

| 通道 | 何时使用 | 实现 |
| --- | --- | --- |
| TCP `127.0.0.1:9090` | 客户端开启 `external-controller` | 裸 `socket.create_connection`（不走 urllib，避免被系统代理影响） |
| Windows 命名管道 | `external-controller-pipe: \\.\pipe\verge-mihomo` | ctypes `CreateFileW` + 手工 HTTP/1.1 + chunked 解析 |

工具会先并行 TCP 端口探测（0.3s 总超时），找不到时自动回落命名管道。
**端口候选取自配置文件 + 一组默认值**，不依赖单一预设。
探测时会依次尝试配置文件里读到的密钥，不会因为第一次 401 就放弃。

---

## 🔧 工作原理

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌──────────┐
│ clients.py  │ →  │  parsers.py  │ →  │ scanner.py  │ →  │  ui.py   │
│ 发现客户端   │    │  解析 YAML    │    │  编排+去重   │    │  呈现    │
└─────────────┘    └──────────────┘    └──────┬──────┘    └──────────┘
                                              │
                                       ┌──────▼──────┐
                                       │ runtime.py  │
                                       │ 运行时探测   │
                                       └─────────────┘
```

1. **发现**（`clients.py`）：按 `CLIENT_DEFS` 匹配进程名与数据目录，
   区分「主程序进程」与「后台服务进程」——**只有服务在跑不算"客户端已打开"**。
2. **解析**（`parsers.py`）：读取 `profiles.yaml` / `profiles.yml` / `config.yaml`，
   带编码容错与加密/损坏检测。解析时对字段做类型防护，**单条脏数据不会让整批配置报废**。
3. **运行时探测**（`runtime.py`）：先并行 TCP 探测，失败回落命名管道，
   拿到核心版本、节点数、当前生效配置、流量与到期。
4. **编排**（`scanner.py`）：合并本地配置与运行时信息，按
   `(client_id, uid, url)` 去重，生成诊断建议。
5. **呈现**（`ui.py`）：脱敏展示（默认打码），提供复制 / 导出 / 导入。

**导入链路**（`importer.py` + `proxymgr.py` + `clashctl.py`）：

```
关进程(含服务) → 关系统代理 → 备份 → 写配置 → 失败回滚
                                          ↓ 成功
                              提示用户更新 → 用户点「恢复代理」
```

---

## 🩺 常见问题与排查

| 现象 | 可能原因 | 排查建议 |
| --- | --- | --- |
| 列表为空 | 客户端用了非默认数据目录（绿色版） | 把配置目录挪到常见路径，或参考 `clients.py` 加新条目 |
| 状态卡"未运行"但后台有进程 | 只有后台服务在跑，主程序没启动 | 启动客户端主程序；`clash-verge-service.exe` / `FlClashHelperService.exe` 这类服务**不算"已打开"** |
| "配置文件疑似已加密" | Clash for Windows 0.20+ 默认加密 | 在 CFW 内关掉配置加密并重新保存 |
| "权限不足" | 在受限账户下运行 | 用有读取 `%APPDATA%` 权限的账户 |
| "未能连接运行时接口" | 控制器被关 / 密钥不对 | 在客户端内开启外部控制器；密钥默认是 `set-your-secret`（出厂默认，不是占位符） |
| 双击 .bat 报一堆乱码 | `.bat` 被错误地存为 UTF-8 | 用记事本"另存为 ANSI 编码"覆盖 |
| 导入时报 `http2 error` / 403 | 系统代理把订阅拉取请求绕去了出口 IP，被服务端中断或拦截 | 用本工具「导入到 Clash」会自动临时关代理；或手动关掉梯子代理、直连家宽后再导入 |
| **导入后要重启 Clash 才生效** | 客户端运行时会覆盖 `profiles.yaml` | 导入前先完全退出 Clash 主程序（含服务），或导入后重启一次再「更新」 |
| **点确认后 Clash 没关** | `clash-verge-service.exe` 会立刻拉起被杀的主进程 | v1.2.7 起导入流程会**连服务一起杀**；杀 Windows 服务需管理员，**右键 exe → 以管理员身份运行** |
| **提示「无法自动关闭，请用任务管理器手动结束」** | 非管理员模式下服务拒绝被终止 | **右键 exe → 以管理员身份运行**；或先手动退出 Clash 再导入；也可按[上文](#-关于管理员权限与-clash-服务)禁用服务 |
| 关工具窗口时代理没恢复 | 导入成功后代理仍处于关闭态 | v1.2.5 起关窗会**弹窗询问**是否恢复，不会静默遗留 |
| 启动很慢 | 第一次扫描需要遍历多个目录 | 仅扫描一次，结果会一直留在表格里；后续可用「一键扫描」手动刷新 |
| 最大化/拉伸时窗口"黑一下" | 之前的修复**打错了窗口**：`winfo_id()` 返回的是 Tk 内部子窗口 `TkChild`，真正的顶层 `TkTopLevel` 从未被修复；且窗口类带 `CS_HREDRAW｜CS_VREDRAW`，会让 resize 时强制全区域擦除 | **v1.2.8 已定位真因**：改对顶层 HWND + 清除重绘标志 + 换类背景画刷。副作用：最大化仍为瞬间切换（关闭了 DWM 缩放动画） |
| 底部"诊断与排查建议"显示不全 | 旧版默认窗口高度不足 | v1.2.6 起默认高度改为 900，最小高度 720 |

---

## 📁 项目结构

```
clash-subscope/
├─ main.py                       入口（设置 DPI awareness 后启动 GUI）
├─ clash-subscope.bat            Windows 启动器（GBK + CRLF）
├─ clash-subscope.spec           PyInstaller 打包配置
├─ requirements.txt              PyYAML / psutil / ttkbootstrap
├─ LICENSE                       MIT
├─ README.md                     本文件
├─ docs/
│  └─ screenshot.png             README 引图
├─ .gitignore                    忽略 _scratch/、__pycache__ 等
└─ clash_sub_tool/
   ├─ __init__.py                包定义与版本号
   ├─ models.py                  数据模型（ClientInfo / SubscriptionItem / RuntimeInfo 等）
   ├─ clients.py                 客户端定义（CLIENT_DEFS）与本机发现
   ├─ parsers.py                 各类 profiles / config 解析
   ├─ scanner.py                 扫描编排与去重
   ├─ runtime.py                 运行时接口（TCP + 命名管道）
   ├─ importer.py                写订阅到客户端（导入功能，唯一写操作）
   ├─ proxymgr.py                Windows 系统代理的临时关闭 / 恢复
   ├─ clashctl.py                检测与关闭 Clash 进程（含服务）
   ├─ formatting.py              脱敏、流量格式化、到期、导出
   ├─ winfix.py                  Win32 层修复（DWM 最大化黑闪）
   └─ ui.py                      tkinter 桌面 GUI（ttkbootstrap / cosmo 主题）
```

> `_scratch/` 是开发期的临时脚本目录，不影响工具运行，已被 `.gitignore` 忽略。

---

## 📝 更新日志

### v1.2.8
- **黑闪真因修复（前几版全部修错了对象）**。
  实测发现 `root.winfo_id()` 返回的是 Tk 内部子窗口 `TkChild`，**不是顶层窗口**；
  真正的顶层是 `TkTopLevel`（需用 `GetAncestor(GA_ROOT)` 上溯）。
  v1.2.3 那套三件套一直作用在 TkChild 上，顶层窗口始终是
  `brush=0x0`（无画刷 → 系统黑）+ `CS_HREDRAW｜CS_VREDRAW`。
- 修复：改对顶层 HWND、**清除 `CS_HREDRAW｜CS_VREDRAW`**（resize 强制全区域擦除，
  Win32 闪烁最经典的根因）、换类背景画刷，并对 TkTopLevel 与 TkChild 两层同时生效。

### v1.2.7
- **修复「点确认后 Clash 没关」**：根因是 `clash-verge-service.exe` 会毫秒级拉起被杀的
  主进程。导入流程现改为**连服务一起终止**，并修正了「找不到目标时静默返回成功」
  的逻辑，失败时明确提示需要管理员权限。

### v1.2.6
- 默认窗口高度 760 → 900，最小高度 640 → 720，底部诊断区首启即可完整显示。

### v1.2.5（第二轮代码复查）
- **关窗未恢复代理**：新增关闭钩子，代理仍待恢复时弹窗询问，避免关窗后代理永久关闭。
- **`name` 为数字时整个客户端订阅全空**：`_short_name` 加类型防护，单条脏数据不再让
  其余配置一起消失。
- 导入中禁用扫描按钮（竞态）、扫描忙时标记补扫、关代理失败清空残留状态、
  备份名加时间戳 + uuid 防撞名、`close_and_wait` 改为按 pid 探测。

### v1.2.4（第一轮代码复查）
- 运行时接口 401 时改为继续尝试已发现的密钥（原先 `break` 导致密钥永不生效）。
- 导入流程移入后台线程，消除主线程 `sleep` 造成的界面冻结。
- 写配置失败自动恢复系统代理。
- `ProxyEnable` 以字符串型 REG_SZ 存储时也能正确识别与还原。
- HTTP 响应读取改用 `bytearray`，消除大响应下的 O(n²)。

### v1.2.3（未能根治，真因见 v1.2.8）
- 尝试修复最大化/拉伸黑闪：类背景画刷 + 关闭 DWM 缩放动画 + 接管 `WM_ERASEBKGND`。
  方向有误且打错了窗口对象，黑闪依旧；v1.2.8 才定位到真因。

### v1.2.0
- 界面重构为 ttkbootstrap / cosmo 现代化主题，替换原生 Win32 控件样式。

### v1.1.x
- 新增「一键导入订阅到 Clash」：自动关 Clash、临时关系统代理、写入 `profiles.yaml`。

---

## 🤝 致谢

- [mihomo / Clash.Meta](https://github.com/MetaCubeX/mihomo) —— 一个能在
  Windows 命名管道上跑 HTTP 外部控制器的优秀核心，本工具的运行时通道完全
  围绕它设计。
- [Clash Verge Rev](https://github.com/clash-verge-rev/clash-verge-rev)
  及其上游，本工具默认兼容它的 `profiles.yaml` 格式。
- 所有 [PyYAML](https://pyyaml.org/) / [psutil](https://github.com/giampaolo/psutil)
  / [ttkbootstrap](https://github.com/israel-dryer/ttkbootstrap)
  / [Tk](https://www.tcl-lang.org/) 的维护者。

---

## 📄 许可证

本项目使用 [MIT License](LICENSE)。简单说：随便用，署名原作者即可，不担
保任何问题。

如果你基于这个工具做了改进版本，欢迎回来提 PR 或在 Issues 告诉我。
