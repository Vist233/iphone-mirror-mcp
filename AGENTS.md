# AGENTS.md · iPhone Mirror MCP

README 给人看；这里给 Agent：装、接、调，以及被拒绝或结果不明时怎么办。操作前先读一遍本文件。

## 接入 MCP

不需要克隆，也不需要建虚拟环境。客户端配置：

```json
{
  "mcpServers": {
    "iphone-local": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/Vist233/iphone-mirror-mcp", "iphone-mirror-mcp"]
    }
  }
}
```

`uvx` 读取仓库里的 `pyproject.toml`，装好 PyObjC 并启动服务器。Pi 可放在 `.pi/mcp.json`，用 `pi mcp list --json` 检查连接；Pi 需启用内置 MCP 扩展，使用 `--no-extensions` 时要显式加 `--extension builtin:mcp`。

已有本地克隆时，也可以直接运行：

```sh
uv run --directory /path/to/iphone-mirror-mcp iphone-mirror-mcp
```

客户端通过 `tools/call` 调用，例如：

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {"name": "mirror_observe", "arguments": {"image": false}}
}
```

这是 MCP 协议请求，不能粘进 shell。服务器的 stdout 只用于 JSON-RPC。

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

CLI 等价命令（由同一个包安装，输出单条 JSON，失败退出码 1，不经过 MCP 事务锁）。在克隆目录用 `uv run mirror-driver`，没有克隆则用 `uvx --from git+https://github.com/Vist233/iphone-mirror-mcp mirror-driver`：

```sh
mirror-driver info
mirror-driver read /tmp/iphone-mirror-read.png
mirror-driver capture /tmp/iphone-mirror-capture.png
mirror-driver home
mirror-driver spotlight
mirror-driver app_switcher
mirror-driver tap 0.5 0.5
mirror-driver text '你好，iPhone'
mirror-driver text '替换内容' replace
mirror-driver type 'Hello'
mirror-driver key return
mirror-driver scroll -20
mirror-driver scroll -200 horizontal
```

`text` 用 Unicode；`type` 用英文布局物理键码。先聚焦输入框。CLI 不会在动作后自动读屏，需要另行 `read`。

也可以在代码里调服务器函数（内部入口，接口未承诺稳定；保留事务锁，动作后自动读屏）：

```python
import json
from iphone_mirror_mcp.server import call

content = call('mirror_observe', {'image': False})
for item in content:
    if item['type'] == 'text':
        print(json.dumps(json.loads(item['text']), ensure_ascii=False, indent=2))
```

## 三条原则

1. **先观察，再动作，动作后再观察。** 每次输入前先 `mirror_observe` 或 `./mirror-driver read`。
2. **`submission: submitted` 不等于成功。** 它只表示事件已提交；手机上的结果要由新的截图或 OCR 确认。
3. **不自动重试，不反向重放，不并发驱动。** 没有移动可能来自列表边界、输入失败或读屏问题，重复执行可能造成重复输入。

## 启动前检查

1. **权限**：宿主程序需要屏幕录制和辅助功能。截图或 OCR 失败通常是屏幕录制缺失；输入被拒通常是辅助功能缺失。权限要授予实际启动工具的程序，不是「iPhone 镜像」本身；修改后按系统提示重启宿主程序。
2. **镜像已连接**：Mac 上打开「iPhone 镜像」并完成连接，iPhone 保持锁屏。
3. **单一驱动**：同一时间只用一个驱动或一个 MCP 事务；多个客户端会互相抢锁。
4. **先只读验证**：`mirror_status` 或 `./mirror-driver info` 检查窗口、焦点和权限；再用 `mirror_observe` 或 `read` 确认 OCR 可用。

## 为什么操作会被拒绝

### 权限不足

- 截图为空或 OCR 失败：屏幕录制权限没有给到宿主程序，或镜像窗口不可截取。
- 事件投递被拒：辅助功能权限没有给到宿主程序。`info` 里的 `trusted_post_event` 不是完整诊断，只代表事件投递预检通过。
- 修改权限后不重启宿主程序，旧权限状态仍会生效。

### 镜像未就绪

以下错误在发送任何输入前出现：

- `Open and connect iPhone Mirroring manually.`：没有找到 iPhone 镜像进程。
- `No portrait mirror window; connection is not confirmed.`：没有找到竖屏镜像窗口。
- `Mirror not ready or screen unreadable; reconnect manually. No event sent.`：OCR 为空，或画面出现「iPhone 正在使用」「锁定 iPhone」「连接已断开」「输入密码」等提示。

处理：恢复连接或锁屏状态，重新 `mirror_observe`。不要在这类错误后继续发送输入。

### 滚动可见性

滚动事件由 WindowServer 按事件记录里的目标点做窗口命中测试，因此镜像窗口必须：

- 在当前桌面；
- 没有最小化、隐藏或被完全遮挡；
- 至少有一块未被其他窗口遮挡的区域。驱动只检查窗口中心线上的横向 50%、纵向 40%、50%、60% 三个候选点；只露出边角可能仍被拒绝；
- 不要求成为前台应用。

找不到候选点时返回 `The mirror is covered by another window; no scroll sent.`，不发送任何滚轮事件。处理：把镜像窗口移到未被遮挡的位置，重新观察，再决定是否滚动。不要换方法或重发。

### 发送过程中焦点或遮挡变化

滚动前和每条记录发送前都会重新检查系统前台、键盘焦点和可见投递点：

- `Mac focus changed; scroll stopped before posting.`
- `Mirror coverage changed; scroll stopped before posting.`

如果第一条记录已发出、第二条被中止，**第一条可能已经生效**。不能当成“完全没做”；先读屏确认手机画面，再决定下一步。

### 设备忙

`Device busy: another MCP transaction holds the phone. No action sent.` 表示另一个 MCP 事务持有每用户文件锁。等待对方结束；不要删锁文件，也不要改用 CLI 绕过锁。CLI 和直接调用驱动本来就不经过这把锁，混用会绕过并发保护。

### 不支持的路由

以下会被明确拒绝且不发送事件：

- 长按、拖拽、多指手势；
- 除 Return/Enter 外的按键和组合键；
- 任意非预设滚动值；
- 非 a1 的滚动方案。

返回 `Unsupported input route; no event sent.` 或对应参数错误。不要改写成底层命令再试。

### 参数错误

- 文本超过 200 个字符或含控制字符：`Text must be <=200 characters without control characters; no implicit Return/submit.`
- `type` 含非英文布局字符：`Unsupported physical key. Use the Unicode text command for non-ASCII text.`
- 滚动值不是 20/50/100/200 的正负值：`Scroll magnitude must be one of 20, 50, 100, 200; use either sign.`
- `dy` 与 `direction`/`magnitude` 混用：`dy cannot be combined with direction or magnitude.`
- 坐标越界：`Coordinate outside window.`

参数错误不会产生手机端效果，修正参数即可。

## 结果怎么读

- `submission: submitted`：事件已提交，效果未确认。
- `phone_effect_verified: false`：必须由下一次观察确认。
- `focus_unchanged` / `cursor_same_at_samples`：采样窗口内系统前台、键盘焦点、光标是否保持不变；不是对所有瞬间的保证。
- 提交后读屏失败：服务器保留提交记录并返回 `retry_action: false`。先重新观察，不要直接重放。
- `record_statuses`：滚动记录被 WindowServer 接受的状态码；0 表示接受，不代表手机一定移动。

## 文本输入

- 先点击或聚焦目标输入框，再输入。
- 默认 Unicode，支持中文和 emoji；`mode: ascii` 使用英文布局物理键码。
- 每次最多 200 个字符，不接受控制字符，不改变剪贴板。
- 不会自动提交；需要回车时单独调用 `mirror_input`，参数 `{"action":"enter"}`。回车可能提交搜索、消息或表单，只在目标明确且用户授权后使用。
- `replace: true` 会替换当前输入框内容，先确认焦点在正确的输入框。

## 滚动

`direction` 表示内容移动方向，不是手指或滚轮方向：

| 参数 | 含义 |
| --- | --- |
| `up` | 内容向上，显示后面的项目；等同于 `dy: 50` |
| `down` | 内容向下，显示前面的项目；等同于 `dy: -50` |
| `left` / `right` | 请求内容向左 / 向右；横向移动已获用户确认，方向映射待核对 |

`50` 是传给 Core Graphics 像素单位滚轮事件的带符号增量，不是手机屏幕坐标，也不是实测位移：纵向为 `(deltaY=±magnitude)`，横向为 `(deltaY=0, deltaX=±magnitude)`。一次请求发送两条相同增量的事件，间隔约 40 毫秒；增量不是手机像素位移，不能把两条当作移动了两倍距离。

四档 20/50/100/200 只是输入预设，不是由屏幕尺寸算出的物理上限。用户在本机报告四档可用、横向 200 能翻页而 100 不能；这不是跨设备阈值。到目标附近改用 20 或 50 小步，每次滚动后读屏确认，不要按固定次数连续发送。

横向使用双轴事件（纵向 0，横向 ±magnitude），不加 Shift。

## 错误速查表

| 错误 | 含义 | 建议动作 |
| --- | --- | --- |
| `Input permission is unavailable; no event sent.` | 辅助功能权限缺失 | 授权并重启宿主程序 |
| `Window capture was empty.` / `OCR failed` | 屏幕录制权限或截图失败 | 检查权限与窗口状态 |
| `Open and connect iPhone Mirroring manually.` | 镜像未启动或未连接 | 手动连接镜像 |
| `No portrait mirror window; connection is not confirmed.` | 没有竖屏镜像窗口 | 确认镜像已连接 |
| `Mirror not ready or screen unreadable` | 未就绪、锁屏提示或断连 | 恢复连接/锁屏后重新观察 |
| `The mirror is covered by another window` | 没有可见投递点 | 把窗口移到未遮挡位置 |
| `Mac focus changed` / `Mirror coverage changed` | 发送中状态变化，可能部分提交 | 先读屏，再决定 |
| `Device busy` | 其他 MCP 事务持有设备锁 | 等待并重新观察 |
| `Unsupported input route` | 未支持的长按/按键/手势 | 改用已支持工具 |
| `Only MIRROR_SCROLL_SCHEME=a1 is published` | 非发布滚动方案 | 使用 a1，不要改环境变量 |

## 不要做的事

- 不要在结果不明时自动重复或反向执行动作。
- 不要为了绕过拒绝而改环境变量、删锁文件或直接调用底层接口。
- 不要并发使用多个驱动、多个客户端，或 CLI 与 MCP 混用。
- 不要在没有读屏确认的情况下连续滚动或连续输入。
