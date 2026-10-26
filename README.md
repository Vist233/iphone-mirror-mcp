# iPhone Mirror MCP

[English](README.en.md)

让支持 MCP 的 AI 客户端，通过 Mac 上的「iPhone 镜像」操作你的 iPhone。

提供读屏、点击、文字输入、主屏与 Spotlight 导航、App 切换器，以及上下和左右滚动接口。无需越狱、开发者模式或安装手机端程序。

项目在 Mac 本地运行，不绑定模型或客户端。可以接入 Pi、Codex 等支持 MCP stdio 的工具；已有 Pi 搭配 DeepSeek Flash 的实际调用记录。

> 当前为实验预览版，仅在一组 Mac/iPhone 上进行过验证。上下滚动已有实测；左右滚动和 App 切换器已实现，仍待真机验收。滚动默认关闭，启用后要求镜像窗口在当前桌面有未被遮挡的区域。

## 能做什么

| 功能 | 当前状态 |
| --- | --- |
| 截图和本地 OCR 识字 | 已验证；不提供 iPhone 原生控件树 |
| 坐标点击、按文字点击 | 已有实测，需检查操作结果 |
| 输入英文、数字、中文和 emoji | 已验证；emoji 曾通过截图核对 |
| 替换输入框文字、显式回车 | 已验证；回车可能提交内容 |
| 返回主屏、打开 Spotlight | 已验证 |
| 上下滚动（a1） | 已有双向实测，默认关闭 |
| 左右滚动、App 切换器 | 已实现，待真机验收 |
| 长按、拖拽、多指手势 | 暂不支持 |

部分成功操作在采样期间保持了 Mac 前台、键盘焦点和鼠标位置不变；其他试验出现过变化。因此，项目尚不能保证所有应用和系统版本下都不干扰电脑操作。详细范围见[验证记录](docs/VALIDATION.md)。

## 它怎么工作

```text
AI / MCP 客户端
    ↓ MCP stdio
server.py              参数校验、设备锁、工具分发、操作后读屏
    ↓
mirror-driver          选择 Python 环境并启动驱动
    ↓
mirror_driver.py       截图、Vision OCR、点击、键盘和滚动事件
    ↓
Mac 上的 iPhone 镜像
    ↓ 苹果负责连接与交互传输
iPhone
```

驱动通过 Mac 操作镜像程序，不直接连接 iPhone 控制协议。读屏使用本地截图和 Apple Vision OCR。运行时不需要模型 API。

## 使用前准备

1. 使用支持「iPhone 镜像」的 Mac 和已配对的 iPhone。
2. 手动连接镜像，确认手机画面可见。
3. 保持 iPhone 锁屏。
4. 为运行工具的宿主程序授予所需的辅助功能和屏幕录制权限。
5. 使用滚动时，让镜像窗口在当前桌面保留未被遮挡的区域。

连接、认证、Face ID 和其他需要用户介入的提示，由用户处理。一次只使用一个手机驱动。

## 安装

在项目目录中执行：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
chmod +x mirror-driver
```

MCP 服务器只使用 Python 标准库；驱动依赖 PyObjC，版本列在 [requirements.txt](requirements.txt)。

启动器默认使用项目的 `.venv/bin/python`。也可以通过 `MIRROR_PYTHON` 指定解释器。启动器不会自动选择某个 pyenv 环境。其他 Mac 上的全新安装仍待验证。

## MCP 配置

将以下路径替换为你的项目绝对路径。本例显式启用实验滚动；删除 `MIRROR_ENABLE_EXPERIMENTAL_INPUT` 后，滚动保持关闭。

```json
{
  "mcpServers": {
    "iphone-local": {
      "command": "/absolute/path/iphone-mirror-mcp/.venv/bin/python",
      "args": ["/absolute/path/iphone-mirror-mcp/server.py"],
      "env": {
        "MIRROR_PYTHON": "/absolute/path/iphone-mirror-mcp/.venv/bin/python",
        "MIRROR_ENABLE_EXPERIMENTAL_INPUT": "1"
      }
    }
  }
}
```

不同客户端的配置入口可能不同，以上为通用配置示例。Pi 可将配置放在项目的 `.pi/mcp.json`，并用 `pi mcp list --json` 检查连接。Pi 需要启用内置 MCP 扩展；使用 `--no-extensions` 时，需显式加入 `--extension builtin:mcp`。

## 工具

| 工具 | 参数与用途 |
| --- | --- |
| `mirror_status` | 无参数；读取窗口、焦点和滚动能力配置 |
| `mirror_observe` | 默认返回 OCR；可选 `image: true` 同时返回截图 |
| `mirror_tap` | `x`、`y` 为窗口归一化坐标，范围均为 `[0,1)` |
| `mirror_tap_text` | `text` 按子串匹配，必须只命中一个 OCR 项 |
| `mirror_navigate` | `destination`：`home`、`spotlight` 或 `app_switcher` |
| `mirror_input` | `action: text` 配合 `text`；可选 `mode: unicode/ascii` 和 `replace`；或只传 `action: enter` |
| `mirror_scroll` | 二选一：`direction: up/down/left/right` 或旧参数 `dy: -50/50` |

0.3.0 将原来的五个导航和输入工具合并为 `mirror_navigate` 与 `mirror_input`。升级后需刷新客户端工具列表，并修改旧工具调用。

文字输入默认使用 Unicode，支持中文和 emoji。`mode: ascii` 使用英文键盘布局的物理键码。输入前先聚焦目标输入框；`replace: true` 会替换当前输入框内容。每次最多输入 200 个字符，不接受控制字符，也不改变剪贴板。

文本输入不会自动提交。需要回车时，单独调用 `mirror_input`，参数为 `{"action":"enter"}`。回车可能提交搜索、消息或表单，只应在目标明确且用户授权后使用。

### 滚动方向

`direction` 表示内容移动方向，不表示手指或滚轮方向：

| 参数 | 含义 |
| --- | --- |
| `up` | 内容向上，显示后面的项目；等同于 `dy: 50` |
| `down` | 内容向下，显示前面的项目；等同于 `dy: -50` |
| `left` / `right` | 请求内容向左 / 向右；实际效果与方向待真机验收 |

每次滚动是固定幅度的一小步，不保证移动 50 个像素，也不保证翻过一整屏。

左右滚动在事件上添加 Shift 标志，不会按下全局 Shift 键。App 切换器使用 Command＋2。这两种操作参考[苹果官方说明](https://support.apple.com/en-us/120421)，但本项目的后台事件路径仍待真机验收。

## 如何检查操作结果

每次操作前先读屏，操作后检查返回的新画面或 OCR。

- `submission: submitted` 只表示事件已提交。
- `phone_effect_verified: false` 表示仍需客户端确认手机上的结果。
- 已提交操作后的读屏失败时，服务器保留提交记录，并返回 `retry_action: false`。

没有移动可能来自列表边界、输入失败或读屏问题。不要自动重复或反向执行结果不明的操作。驱动报错或超时，也可能已对手机产生部分影响。

## 实现与限制

点击使用面向目标进程的 SkyLight 事件记录。键盘输入会先准备镜像程序内部的激活和接收窗口状态，再发送面向目标进程的事件。

a1 滚动通过 `SLSPostEventRecord` 提交两条像素滚轮记录，间隔约 40 毫秒。每条记录包含目标点。上下滚动路径不准备内部激活，不主动切换系统前台或移动鼠标。发送期间若检测到前台、键盘焦点或窗口遮挡变化，驱动会停止继续提交。

当前只发布 a1 路径；其他 `MIRROR_SCROLL_SCHEME` 值会被拒绝。隐藏、完全遮挡、最小化或位于其他桌面的镜像，尚未通过滚动验收。

SkyLight 函数和事件记录布局属于私有接口，可能随 macOS 版本变化。焦点和鼠标约每 25 毫秒采样一次，不能覆盖所有瞬间。OCR 可能合并文字、误读图标或 emoji。

每用户文件锁会串行处理本 MCP 的多个实例，但无法协调其他驱动、直接 CLI 调用或用户操作。跨机器、跨系统版本和长时间无人值守运行仍待验证。

## 测试

```sh
python3 -m unittest -v test_server.py
```

当前有 28 项离线测试，检查协议、参数校验、工具分发和驱动保护逻辑，不向手机发送输入。真机证据和未验证项见[验证记录](docs/VALIDATION.md)。

实验文件、截图、录像、模型会话、本地运行环境和私人岗位数据不随项目分发。

## 致谢与许可证

底层 SkyLight 事件记录实现参考了 [phone-harness](https://github.com/ShawnPana/phone-harness)，特别是其 `background.py` 中的记录布局。项目保留了它的 [MIT 版权与许可证](third_party/phone-harness-LICENSE)。[yabai](https://github.com/koekeishiya/yabai) 是 make-key 方法的间接参考，来源于 phone-harness 的引用。

[mirroir-mcp](https://github.com/jfarcand/mirroir-mcp) 和 [GUIWeave](https://github.com/hyechow/GUIWeave) 提供了对照与研究参考。它们不是运行依赖，本项目不会启动这些项目。

来源说明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。本项目采用 [MIT 许可证](LICENSE)。

中文为主文档，英文版根据中文同步维护。
