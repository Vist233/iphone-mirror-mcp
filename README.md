# iPhone Mirror MCP

[English](README.en.md)

让支持 MCP 的 AI 客户端，通过 Mac 上的「iPhone 镜像」操作你的 iPhone。

提供读屏、点击、文字输入、主屏与 Spotlight 导航、App 切换器，以及上下和左右滚动接口。无需越狱、开发者模式或安装手机端程序。

项目在 Mac 本地运行，不绑定模型或客户端。可以接入 Pi、Codex 等支持 MCP stdio 的工具；已有 Pi 搭配 DeepSeek Flash 的实际调用记录。

> 当前为实验预览版，仅在一组 Mac/iPhone 上进行过验证。上下滚动已有实测；横向滚动已由用户确认有效，左右方向映射仍待核对；App 切换器待真机验收。滚动默认关闭，启用后要求镜像窗口在当前桌面有未被遮挡的区域。

## 使用条件

- 使用支持「iPhone 镜像」的 Mac，以及已完成配对的 iPhone。先手动连接镜像，并保持 iPhone 锁屏。
- **上下、左右滚动都必须让镜像可视**：窗口在当前桌面，不能最小化、隐藏或被完全遮挡；不要求镜像成为前台应用。
- 当前实现检查窗口中心线上的三个候选点。至少一个候选点必须未被其他窗口遮挡；仅露出窗口边缘也可能无法滚动。
- 找不到可见投递点时，驱动报错，不发送滚轮事件。发送期间如果投递点或 Mac 前台/键盘焦点发生变化，会停止继续发送；此前已发送的事件仍可能产生效果。
- 运行工具的宿主程序需要屏幕录制和辅助功能权限，具体见下文。
- 一次只使用一个手机驱动。操作后根据新截图或 OCR 确认结果。

上下滚动已有实测，横向移动获用户确认；左右方向映射和 App 切换器仍待验收。长按、拖拽和多指手势暂不支持。

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

## 安装

在项目目录中执行：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
chmod +x mirror-driver
```

MCP 服务器只使用 Python 标准库；驱动依赖 PyObjC，版本列在 [requirements.txt](requirements.txt)。

启动器默认使用项目的 `.venv/bin/python`。也可以通过 `MIRROR_PYTHON` 指定解释器。启动器不会自动选择某个 pyenv 环境。其他 Mac 上的全新安装仍待验证。

## 三种调用方式

三种方式使用相同的驱动，但入口和当前返回内容不同。以下只描述已有用法；分模式输出的后续方案见[接口整理草案](docs/INTERFACE-DESIGN.md)。

### Terminal / 命令行

在项目目录执行。`info` 只检查窗口、焦点和输入权限，不发送手机输入；`read` 保存截图并返回 OCR。

```sh
./mirror-driver info
./mirror-driver read /tmp/iphone-mirror-read.png
./mirror-driver capture /tmp/iphone-mirror-capture.png
```

操作命令如下。每次只执行需要的一条，并先确认当前手机页面：

```sh
./mirror-driver home
./mirror-driver spotlight
./mirror-driver app_switcher
./mirror-driver tap 0.5 0.5
./mirror-driver text '你好，iPhone'
./mirror-driver text '替换内容' replace
./mirror-driver type 'Hello'
```

`text` 使用 Unicode；`type` 使用英文布局物理键码。先聚焦输入框。只有确认需要提交时，才执行 `./mirror-driver key return`。

当前版本滚动仍需设置实验开关。支持20、50、100、200四档及其负值；以下分别为纵向小步和横向翻页请求，反向使用相反符号：

```sh
MIRROR_ENABLE_EXPERIMENTAL_INPUT=1 ./mirror-driver scroll -20
MIRROR_ENABLE_EXPERIMENTAL_INPUT=1 ./mirror-driver scroll -200 horizontal
```

CLI 当前向 stdout 输出一条 JSON，失败时退出码为 1；没有面向人的简洁排版。操作命令本身不会自动返回操作后的 OCR，需另行 `read`。直接调用驱动也不经过 MCP 的事务锁。

### Code mode / 在代码中组合调用

当前没有独立的 code-mode SDK。可以在项目目录用 Python 调用现有 `server.call()`；这是内部代码入口，接口尚未承诺稳定。它保留设备事务锁，操作后会自动读屏；`server` 模块无需额外 MCP Python SDK。

```sh
.venv/bin/python - <<'PY'
import json
from server import call

content = call('mirror_observe', {'image': False})
for item in content:
    if item['type'] == 'text':
        print(json.dumps(json.loads(item['text']), ensure_ascii=False, indent=2))
PY
```

返回值目前是 MCP content 列表，文字项中的 JSON 还需解析。它不是专门设计的代码对象接口。调用滚动时，当前也需在进程环境中设置实验开关。

### MCP / 让客户端调用工具

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

客户端通过 `tools/call` 请求工具，例如：

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "mirror_observe",
    "arguments": {"image": false}
  }
}
```

这是 MCP 协议请求，不是可以直接粘贴进 shell 的命令。`server.py` 的 stdin/stdout 用于 JSON-RPC 通信；不要在其 stdout 中混入终端提示。MCP 当前返回 text/image content；操作成功提交后会追加 OCR，读屏失败时保留提交记录。

## 工具

| 工具 | 参数与用途 |
| --- | --- |
| `mirror_status` | 无参数；读取窗口、焦点和滚动能力配置 |
| `mirror_observe` | 默认返回 OCR；可选 `image: true` 同时返回截图 |
| `mirror_tap` | `x`、`y` 为窗口归一化坐标，范围均为 `[0,1)` |
| `mirror_tap_text` | `text` 按子串匹配，必须只命中一个 OCR 项 |
| `mirror_navigate` | `destination`：`home`、`spotlight` 或 `app_switcher` |
| `mirror_input` | `action: text` 配合 `text`；可选 `mode: unicode/ascii` 和 `replace`；或只传 `action: enter` |
| `mirror_scroll` | `direction: up/down/left/right`，可选 `magnitude: 20/50/100/200`（默认50）；或只传纵轴旧参数 `dy`，取四档的正负值 |

例如，MCP横向翻页工具调用为：

```json
{"name":"mirror_scroll","arguments":{"direction":"left","magnitude":200}}
```

这是客户端工具调用的名称与参数，不是终端命令。旧参数 `dy` 不能与 `direction` 或 `magnitude` 混用；Code mode的 `server.call()` 使用同样的工具参数。

0.3.0 将原来的五个导航和输入工具合并为 `mirror_navigate` 与 `mirror_input`。升级后需刷新客户端工具列表，并修改旧工具调用。

文字输入默认使用 Unicode，支持中文和 emoji。`mode: ascii` 使用英文键盘布局的物理键码。输入前先聚焦目标输入框；`replace: true` 会替换当前输入框内容。每次最多输入 200 个字符，不接受控制字符，也不改变剪贴板。

文本输入不会自动提交。需要回车时，单独调用 `mirror_input`，参数为 `{"action":"enter"}`。回车可能提交搜索、消息或表单，只应在目标明确且用户授权后使用。

### 滚动方向

`direction` 表示内容移动方向，不表示手指或滚轮方向：

| 参数 | 含义 |
| --- | --- |
| `up` | 内容向上，显示后面的项目；等同于 `dy: 50` |
| `down` | 内容向下，显示前面的项目；等同于 `dy: -50` |
| `left` / `right` | 请求内容向左 / 向右；横向移动已获用户确认，方向映射待核对 |

### `50` 是什么，距离怎么选

当前 `50` 是传给 Core Graphics 像素单位滚轮事件的带符号增量，不是手机屏幕坐标，也不是内容实测位移。正负号决定事件方向。四档使用相同构造：纵轴为 `(deltaY=±magnitude)`，横轴为 `(deltaY=0, deltaX=±magnitude)`。

一次请求会发送两条相同增量的事件，间隔约 40 毫秒。因此，它既不是“总共移动 50 像素”，也不能把两条事件直接当作手机内容移动 100 像素。镜像转换、目标 App、列表边界和分页吸附都会影响结果。

正式CLI和MCP开放20、50、100、200四档，不是由屏幕宽高计算出来的物理最大值。用户在本机报告四档均可用，且**横向200能翻页，100不能翻页**。该阈值不保证适用于其他设备、App或窗口尺寸；本轮没有取得四档的仪器化位移数据。

| 增量档位 | 选用方式 |
| --- | --- |
| 20 | 较小输入步进，可先用于靠近目标时的微调 |
| 50 | 原有默认步进，省略MCP的 `magnitude` 时使用 |
| 100 | 较大输入步进；本机反馈横向不足以翻页 |
| 200 | 本机反馈横向可翻页；纵向实际跨度需看返回画面 |

如果要提供“滚半屏/一屏”，更适合在上层使用**可视内容区域比例**：纵向参考内容区高度，横向参考内容区宽度；不包含窗口标题栏。滚轮增量与内容位移之间需要实测映射，不能直接相等。拖拽手势的起终点受屏幕范围约束，但本项目当前发送的是滚轮事件。

我们的建议是：普通列表先以约 0.7 个可视区域为目标，保留上下文重叠；到目标附近改用小步，读屏确认后再继续。这是待实现和标定的产品方案，不是 Apple 规定，也不是当前已支持的 `amount` 参数。当前先使用四档预设；分页界面仍需检查是否真正翻页。

Core Graphics 对事件单位及增量的定义见[滚动单位](https://developer.apple.com/documentation/coregraphics/cgscrolleventunit)和[事件构造接口](https://developer.apple.com/documentation/coregraphics/cgeventcreatescrollwheelevent)。

横向滚动创建双轴事件：纵向增量为0，横向增量取所选档位的正负值，不添加Shift标志。此前Shift＋纵向滚轮方案被用户反馈为仍然上下移动，已替换。用户在本机确认双轴方案和200翻页有效；这不等于完整双向、跨应用验收。

App 切换器使用 Command＋2，参考[苹果官方说明](https://support.apple.com/en-us/120421)；本项目的后台事件路径仍待真机验收。

### 实验开关是否保留

`MIRROR_ENABLE_EXPERIMENTAL_INPUT=1` 是早期保留的输入路径开关，不是“允许不可见时滚动”。无论是否设置，都不能绕过滚动的可见性检查。

后续建议取消已接入滚动在日常使用中的显式实验开关，改为默认按条件执行。条件不满足时应报错，说明未执行；不要静默跳过或返回成功。逐条发送前的可见性与焦点检查继续保留，其他未支持输入路径仍应拒绝。本轮先整理方案，当前代码及示例中的开关尚未删除。

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

当前有30项离线测试，检查协议、参数校验、工具分发和驱动保护逻辑，包括四档正负值、两个轴及增量构造，不向手机发送输入。真机证据和未验证项见[验证记录](docs/VALIDATION.md)。

实验文件、截图、录像、模型会话、本地运行环境和私人岗位数据不随项目分发。

## 致谢与许可证

底层 SkyLight 事件记录实现参考了 [phone-harness](https://github.com/ShawnPana/phone-harness)，特别是其 `background.py` 中的记录布局。项目保留了它的 [MIT 版权与许可证](third_party/phone-harness-LICENSE)。[yabai](https://github.com/koekeishiya/yabai) 是 make-key 方法的间接参考，来源于 phone-harness 的引用。

[mirroir-mcp](https://github.com/jfarcand/mirroir-mcp) 和 [GUIWeave](https://github.com/hyechow/GUIWeave) 提供了对照与研究参考。它们不是运行依赖，本项目不会启动这些项目。

来源说明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。本项目采用 [MIT 许可证](LICENSE)。

中文为主文档，英文版根据中文同步维护。
