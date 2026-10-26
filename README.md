# iPhone Mirror MCP

[English](README.en.md)

**iPhone Mirror MCP** 是一个本地运行的 MCP（Model Context Protocol）服务器，让 Claude Code、Codex、Pi 等支持 MCP 的 AI 客户端通过 macOS 的「iPhone 镜像」读取并操作 iPhone 屏幕。已有 Pi 搭配 DeepSeek Flash 的真实调用记录。

常见做法是把镜像窗口切到前台，或移动系统指针后再发送事件；本项目不这样做：点击、文字输入和导航都以目标进程或目标窗口为投递目标，不切换系统前台、不改变键盘焦点、不移动鼠标。

条件同样明确：输入前会先本地截图并用 Apple Vision OCR 判断页面状态；**滚动要求镜像窗口在当前桌面可见，且至少有一块未被其他窗口遮挡的区域**（不要求是前台窗口）。不需要越狱、开发者模式或安装手机端程序。

> 实验预览状态：上下滚动已有实测；横向移动获用户确认，左右方向映射仍待核对；App 切换器待真机验收。滚动默认可用，但仍受可见性检查约束。

## 快速开始

把这一句发给你的 AI Agent：

> [!TIP]
> 按 https://github.com/Vist233/iphone-mirror-mcp 配置好，让我用它操作 iPhone。

人只做两件事：开权限（见[需要哪些权限](#需要哪些权限)）、连上「iPhone 镜像」并锁屏。其余交给 Agent。

## 需要哪些权限

在 macOS「系统设置 → 隐私与安全性」中，为实际启动工具的宿主程序开启：

| 权限 | 用途 |
| --- | --- |
| 屏幕录制 / 屏幕与系统音频录制 | 截取 iPhone 镜像窗口，供 OCR 和图片观察使用；本项目不采集音频 |
| 辅助功能 / 设备控制相关权限 | 读取镜像的辅助功能状态，并投递点击、键盘和滚轮事件 |

权限页面名称随 macOS 版本和语言变化。在 Terminal 或 iTerm 中启动时，检查对应终端；由 Codex 或其他 MCP 客户端启动时，检查对应客户端。以系统提示列出的责任程序为准，不能只给「iPhone 镜像」开权限。

修改权限后，按系统提示退出并重新打开宿主程序。驱动会检查输入事件投递权限，但 `info` 中的 `trusted_post_event` 不是完整权限诊断；仍需通过一次 `read` 确认截图和 OCR 可用。

当前发布代码不监听全局键盘或滚轮，因此不把「输入监控」列为运行必需权限；也不要求完全磁盘访问、麦克风或 Apple Events 自动化权限。连接、认证和 Face ID 等提示由用户处理。

设置入口参考苹果的[辅助功能权限说明](https://support.apple.com/en-euro/guide/mac-help/mh43185/27/mac/27)与[屏幕录制权限说明](https://support.apple.com/en-gb/guide/mac-help/mchl592e5686/mac)。

## 使用条件

1. 已连接「iPhone 镜像」，iPhone 保持锁屏。
2. 滚动时镜像窗口必须露出来：在当前桌面，且至少有一块未被其他窗口遮挡的区域；不要求成为前台应用。

为什么会有这些条件、失败后怎么处理，见[给 AI 的详细说明](#给-ai-的详细说明)。

## 数据与隐私：什么会离开你的 Mac

项目自身不发起网络请求：不需要模型 API、账号或 API key，也没有遥测、崩溃上报或分析 SDK。以下内容会交给调用它的 MCP 客户端：

| 内容 | 来源 | 说明 |
| --- | --- | --- |
| OCR 文本行 | `mirror_observe` | 屏幕文字、置信度、归一化坐标 |
| 截图 | `mirror_observe` 且 `image: true` | PNG，base64 编码 |
| 窗口与焦点元数据 | `mirror_status`、操作结果 | 窗口 ID 与尺寸、前后台 PID、键盘焦点、光标坐标、输入权限状态 |

- 客户端如果使用云端模型，这些内容会像普通对话一样发送到模型服务；是否上传、上传到哪里由客户端和你的配置决定，本项目不参与也不记录。
- 截图只在两处落盘：CLI 的 `read`、`capture` 写到调用者指定的路径；MCP 使用临时目录，OCR 后随函数返回删除，不会常驻。
- OCR 读取的是整屏可见文字，可能包含私信、验证码或通知内容。接入前应确认客户端的数据处理方式。
- 项目不读剪贴板、不采集音频、不监听全局键盘或滚轮，也不接触相册和通知。

## 它怎么工作

```text
AI / MCP 客户端
    ↓ MCP stdio
iphone_mirror_mcp.server   参数校验、设备锁、工具分发、操作后读屏
    ↓ 启动驱动进程
iphone_mirror_mcp.driver   截图、Vision OCR、点击、键盘和滚动事件
    ↓
Mac 上的 iPhone 镜像
    ↓ 苹果负责连接与交互传输
iPhone
```

驱动通过 Mac 操作镜像程序，不直接连接 iPhone 控制协议。读屏使用本地截图和 Apple Vision OCR。运行时不需要模型 API。

## 给 AI 的详细说明

人只需要上面两条条件。Agent 按需读 [AGENTS.md](AGENTS.md)：安装、接入、调用参数，以及权限失败、可见性判断、部分提交和重试规则都在那里。

## 工具

| 工具 | 参数与用途 |
| --- | --- |
| `mirror_status` | 无参数；读取窗口、焦点和滚动能力配置 |
| `mirror_observe` | 默认返回 OCR；可选 `image: true` 同时返回截图 |
| `mirror_tap` | `x`、`y` 为窗口归一化坐标，范围均为 `[0,1)` |
| `mirror_tap_text` | `text` 按子串匹配，必须只命中一个 OCR 项 |
| `mirror_navigate` | `destination`：`home`、`spotlight` 或 `app_switcher` |
| `mirror_input` | `action: text` 配合 `text`；可选 `mode: unicode/ascii` 和 `replace`；或只传 `action: enter` |
| `mirror_scroll` | `direction: up/down/left/right`，可选 `magnitude: 20/50/100/200`（默认 50）；或只传纵轴旧参数 `dy` |

参数细节、CLI 命令和滚动档位说明见 [AGENTS.md](AGENTS.md)。

## 常见问题（FAQ）

### 必须先授予权限吗？不授权会怎样？

必须授予。没有屏幕录制，驱动无法截图和 OCR，会在发送任何输入前拒绝操作；没有辅助功能，点击、键盘和滚轮事件都无法投递。权限要授予实际启动工具的宿主程序（终端或 MCP 客户端），只给「iPhone 镜像」开权限无效。修改后按系统提示重启宿主程序。

### 使用时会不会抢占前台、移动我的鼠标？

不会。驱动不使用全局 `CGEventPost`，不 warp 指针，也不把镜像切到系统前台；点击、键盘和滚动都定向投递给镜像进程或窗口。操作返回中的 `focus_unchanged`、`cursor_same_at_samples` 和 25 毫秒采样记录可供核对。边界见[给 AI 的详细说明](#给-ai-的详细说明)：采样不能覆盖所有瞬间，部分历史试验出现过光标变化，跨应用、跨版本仍待验证。

### 滚动为什么要求窗口可见，点击却不用？

滚动事件由 WindowServer 按事件记录里的目标点做窗口命中测试，找不到属于镜像的可见点就无处投递，所以驱动在发送前检查并报错，而不是把事件发给别的窗口。点击和键盘直接投递给镜像进程，不依赖命中测试。

### 需要越狱、开发者模式或安装手机端程序吗？

都不需要。项目只使用 Mac 上系统自带的「iPhone 镜像」和本地 PyObjC，不向 iPhone 安装任何程序。

### 支持 Windows 或 Linux 吗？没有 Mac 能用吗？

不支持。实现依赖 macOS 私有 SkyLight 接口和「iPhone 镜像」，没有跨平台路径。

### 能接哪些 AI 客户端？

任何支持 MCP stdio 的客户端，例如 Claude Code、Codex、Pi。已有 Pi 搭配 DeepSeek Flash 的真实调用记录；接入方式见 [AGENTS.md](AGENTS.md)，由 Agent 自行完成。

### 会把我的屏幕内容上传到云端吗？

项目自身不联网。OCR 文本、可选截图和窗口元数据会交给 MCP 客户端；客户端如果使用云端模型，这些内容会随对话发送，由客户端和你的配置决定。MCP 路径下的截图只存在于临时目录，OCR 后即删除。

### 支持长按、拖拽和多指手势吗？滚动不动怎么办？

长按、拖拽和多指手势都不支持。滚动不动可能来自列表边界、输入失败或读屏问题；不要自动重复或反向执行结果不明的操作，先读屏确认。

### 是免费的吗？能无人值守运行吗？

使用 MIT 许可证，免费使用和修改。当前是实验预览：只在一组 Mac/iPhone 上验证，跨机器、跨系统版本和长时间无人值守运行尚未验证。

## 验证与限制

只在一组 Mac/iPhone 上验证；焦点和光标采样约 25 毫秒一次，不能覆盖所有瞬间。跨机器、跨系统版本和长时间无人值守运行尚未验证。实验文件、截图、录像、模型会话和本地运行环境不随项目分发。

## 致谢与许可证

底层 SkyLight 事件记录实现参考了 [phone-harness](https://github.com/ShawnPana/phone-harness)，特别是其 `background.py` 中的记录布局；它的 MIT 版权与许可证全文在 [NOTICE](NOTICE)。[yabai](https://github.com/koekeishiya/yabai) 是 make-key 方法的间接参考，来源于 phone-harness 的引用。

[mirroir-mcp](https://github.com/jfarcand/mirroir-mcp) 和 [GUIWeave](https://github.com/hyechow/GUIWeave) 提供了对照与研究参考。它们不是运行依赖，本项目不会启动这些项目。

第三方来源与许可证全文见 [NOTICE](NOTICE)。本项目采用 [MIT 许可证](LICENSE)。

中文为主文档，英文版根据中文同步维护。
