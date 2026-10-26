# iPhone Mirror MCP

[中文](README.md)

Let an AI client that supports MCP operate your iPhone through Apple's iPhone Mirroring on a Mac.

The project provides screen reading, taps, text input, Home and Spotlight navigation, App Switcher, and vertical and horizontal scroll interfaces. No jailbreak, developer mode, or phone-side runner is required.

It runs locally on the Mac and is not tied to a model or client. It can connect to clients such as Pi and Codex through MCP stdio. Actual Pi calls with a configured DeepSeek Flash provider have been recorded.

> This is an experimental preview, tested on one Mac/iPhone pair. Vertical scrolling has device evidence. The user confirmed horizontal movement; exact left/right mapping still awaits validation. App Switcher awaits device acceptance. Scrolling is off by default. When enabled, it requires an uncovered area of the mirror on the current desktop.

## Conditions for use

- Use a Mac that supports iPhone Mirroring and a paired iPhone. Connect manually and keep the iPhone locked.
- **Both vertical and horizontal scrolling require a visible mirror** on the current desktop. It must not be minimized, hidden, or fully covered. It does not need to be the foreground app.
- The implementation checks three candidate points on the window's center line. At least one must be uncovered. An exposed window edge alone may not suffice.
- If no candidate is available, the driver reports an error without sending wheel events. It stops further submission if the target point, Mac foreground, or keyboard focus changes. Previously submitted events may still take effect.
- The host application needs screen recording and Accessibility permissions, as described below.
- Use only one phone driver at a time. Check the fresh screenshot or OCR after each action.

Vertical scrolling has device evidence, and the user confirmed horizontal movement. Exact left/right mapping and App Switcher await acceptance. Long press, dragging, and multi-touch are not supported.

Some successful actions preserved sampled Mac foreground, keyboard focus, and cursor position. Other trials contained changes. The project cannot guarantee uninterrupted desktop use across all apps or OS versions. See the [validation record](docs/VALIDATION.md).

## How it works

```text
AI / MCP client
    ↓ MCP stdio
server.py              Parameter validation, device lock, dispatch, observation
    ↓
mirror-driver          Selects Python and starts the driver
    ↓
mirror_driver.py       Capture, Vision OCR, taps, keyboard and scroll events
    ↓
iPhone Mirroring on Mac
    ↓ Apple handles the connection and interaction transport
iPhone
```

The driver operates the mirror on the Mac. It does not connect directly to an iPhone control protocol. Screenshots and Apple Vision OCR provide observations. No model API is required at runtime.

## Required permissions

In macOS System Settings → Privacy & Security, enable these permissions for the application that actually launches the tool:

| Permission | Purpose |
| --- | --- |
| Screen Recording / Screen & System Audio Recording | Capture the mirror for OCR and image observation; this project does not capture audio |
| Accessibility / related device-control permission | Read the mirror's accessibility state and submit taps, keyboard input, and wheel events |

Names vary by macOS version and language. When launching from Terminal or iTerm, check that terminal's permissions. When launching from Codex or another MCP client, check that client. Follow the responsible application named by macOS; permission for iPhone Mirroring alone is insufficient.

After changing permissions, quit and reopen the host if macOS requests it. The driver checks event-posting permission. The `trusted_post_event` field from `info` is not a complete permissions check. Use `read` to check capture and OCR as well.

Published code does not monitor global keyboard or wheel input, so Input Monitoring is not a runtime requirement. Full Disk Access, microphone access, and Apple Events Automation are not required by the current implementation. The user handles connection, authentication, and Face ID prompts.

See Apple's instructions for [Accessibility](https://support.apple.com/en-euro/guide/mac-help/mh43185/27/mac/27) and [screen recording](https://support.apple.com/en-gb/guide/mac-help/mchl592e5686/mac).

## Installation

Run these commands in the project directory:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
chmod +x mirror-driver
```

The MCP server uses only the Python standard library. The driver requires PyObjC. Pinned versions are in [requirements.txt](requirements.txt).

The launcher uses the project's `.venv/bin/python` by default. Set `MIRROR_PYTHON` to select another interpreter. The launcher does not automatically select a named pyenv environment. Fresh installation on another Mac remains unverified.

## Three ways to call the project

The three modes share a driver but have different entry points and current return values. The following examples describe existing behavior. Future output design is in the [interface draft (Chinese)](docs/INTERFACE-DESIGN.md).

### Terminal / CLI

Run commands in the project directory. `info` checks the window, focus, and event-posting permission without phone input. `read` saves a screenshot and returns OCR.

```sh
./mirror-driver info
./mirror-driver read /tmp/iphone-mirror-read.png
./mirror-driver capture /tmp/iphone-mirror-capture.png
```

Run only the required action after checking the phone screen:

```sh
./mirror-driver home
./mirror-driver spotlight
./mirror-driver app_switcher
./mirror-driver tap 0.5 0.5
./mirror-driver text '你好，iPhone'
./mirror-driver text '替换内容' replace
./mirror-driver type 'Hello'
```

`text` uses Unicode. `type` uses physical English-layout keycodes. Focus the field first. Run `./mirror-driver key return` only when submission is intended and authorized.

Scrolling currently requires the experimental flag. Presets are 20, 50, 100, and 200, with either sign. These examples request a small vertical step and a horizontal page action. Reverse the sign for the opposite direction:

```sh
MIRROR_ENABLE_EXPERIMENTAL_INPUT=1 ./mirror-driver scroll -20
MIRROR_ENABLE_EXPERIMENTAL_INPUT=1 ./mirror-driver scroll -200 horizontal
```

The CLI currently prints one JSON object to stdout and exits with code 1 on failure. It has no concise human-readable format. Actions do not automatically return subsequent OCR; call `read` separately. Direct driver calls also bypass the MCP transaction lock.

### Code mode / composing calls in code

There is no dedicated code-mode SDK. Python can call the existing `server.call()` from the project directory. This is an internal entry point without a stable API commitment. It preserves the device transaction lock and observes after actions. The `server` module requires no MCP Python SDK.

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

The return value is currently a list of MCP content items. JSON inside text items needs another parsing step. This is not a dedicated object API. Scroll calls still require the experimental flag in the process environment.

### MCP / client tool calls

Replace the paths with absolute paths to your checkout. This example explicitly enables experimental scrolling. Omit `MIRROR_ENABLE_EXPERIMENTAL_INPUT` to leave scrolling disabled.

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

Configuration locations vary by client. The example above uses a common format. Pi can use the project's `.pi/mcp.json`. Check the connection with `pi mcp list --json`. Pi's built-in MCP extension must be enabled. With `--no-extensions`, explicitly include `--extension builtin:mcp`.

A client sends a `tools/call` request, for example:

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

This is an MCP protocol request, not a shell command. `server.py` uses stdin/stdout for JSON-RPC; human-readable prompts must not appear on stdout. MCP currently returns text/image content. Submitted actions append OCR, and observation failures preserve the submission report.

## Tools

| Tool | Arguments and purpose |
| --- | --- |
| `mirror_status` | No arguments; reports window, focus, and scroll configuration |
| `mirror_observe` | OCR by default; optional `image: true` also returns a screenshot |
| `mirror_tap` | Normalized window coordinates `x` and `y`, each in `[0,1)` |
| `mirror_tap_text` | `text` is a substring that must match exactly one OCR item |
| `mirror_navigate` | `destination`: `home`, `spotlight`, or `app_switcher` |
| `mirror_input` | `action: text` with `text`, optional `mode: unicode/ascii` and `replace`; or `action: enter` alone |
| `mirror_scroll` | `direction: up/down/left/right`, optional `magnitude: 20/50/100/200` (default 50); or vertical legacy `dy` alone, using either sign of these presets |

For example, an MCP horizontal page tool call is:

```json
{"name":"mirror_scroll","arguments":{"direction":"left","magnitude":200}}
```

This is a tool name and arguments, not a shell command. Legacy `dy` cannot be combined with `direction` or `magnitude`. Code-mode `server.call()` uses the same tool arguments.

Version 0.3.0 consolidates five previous navigation and input tools into `mirror_navigate` and `mirror_input`. Refresh the client's tool list after upgrading and update old calls.

Text input uses Unicode by default and supports Chinese and emoji. `mode: ascii` uses physical keycodes for an English keyboard layout. Focus the target field first. `replace: true` replaces its contents. Each call accepts up to 200 characters, rejects control characters, and leaves the clipboard unchanged.

Text input never submits automatically. To press Return, call `mirror_input` separately with `{"action":"enter"}`. Return can submit a search, message, or form. Use it only with an identified target and user authorization.

### Scroll direction

`direction` describes content movement, not finger or wheel movement:

| Argument | Meaning |
| --- | --- |
| `up` | Content moves up to reveal later items; equivalent to `dy: 50` |
| `down` | Content moves down to reveal earlier items; equivalent to `dy: -50` |
| `left` / `right` | Requests content movement left / right; user confirmed horizontal movement, exact mapping awaits validation |

### What does 50 mean?

`50` is the signed delta passed to a Core Graphics wheel event using pixel units. It is not a phone coordinate or measured content displacement. The sign selects event direction. All four presets use the same construction: `(deltaY=±magnitude)` vertically and `(deltaY=0, deltaX=±magnitude)` horizontally.

Each request sends two equal-delta events about 40ms apart. It guarantees neither 50 nor 100 pixels of phone content movement. Mirroring conversion, the target app, list boundaries, and page snapping affect the result.

The CLI and MCP accept four magnitudes: 20, 50, 100, and 200. They are not physical maxima derived from screen dimensions. The user reports all four work on their setup, and **horizontal 200 flips a page while 100 does not**. This threshold is not guaranteed on other devices, apps, or window sizes. No instrumented displacement dataset for all four presets was collected in this revision.

| Magnitude | Suggested use |
| --- | --- |
| 20 | Smaller input step; a starting point for fine adjustment near a target |
| 50 | Existing default when MCP `magnitude` is omitted |
| 100 | Larger input step; user reports it is insufficient for horizontal page changes |
| 200 | User reports horizontal page changes; inspect the screen for vertical displacement |

For “half a screen” or “one screen,” an upper-level interface should express a fraction of the visible content area. Vertical actions refer to content height; horizontal actions refer to width, excluding window chrome. Event delta needs measured calibration to content movement. It cannot be assumed equal. Drag endpoints are constrained by screen geometry, but this project sends wheel events.

Our proposal is to target about 0.7 of the visible area for ordinary lists, preserving context overlap. Near a target, use smaller steps and inspect observations. This is a design proposal awaiting implementation and calibration, not an Apple rule or an existing `amount` parameter. Use the four presets for now; paged interfaces still need page-change checks.

See Apple's definitions of [scroll units](https://developer.apple.com/documentation/coregraphics/cgscrolleventunit) and the [event constructor](https://developer.apple.com/documentation/coregraphics/cgeventcreatescrollwheelevent).

Horizontal scrolling creates a two-axis event: zero vertical delta and the selected signed horizontal magnitude, without a Shift flag. The user reported that the previous Shift+vertical-wheel approach still moved vertically. That approach has been replaced. The user confirmed the two-axis approach and page changes with 200. This is not a complete bidirectional or cross-app acceptance result.

App Switcher uses Command+2, as described in [Apple's documentation](https://support.apple.com/en-us/120421). Its background event path in this project still awaits device acceptance.

### Keep the experimental flag?

`MIRROR_ENABLE_EXPERIMENTAL_INPUT=1` is an early input-route gate, not permission to scroll an invisible mirror. It never bypasses the visibility check.

We propose removing this explicit flag from routine use of the integrated scroll route. Execute only when conditions hold; otherwise return an error that explains non-execution. Do not silently skip or report success. Preserve checks before each event and reject unsupported input routes. This revision only documents the proposal; the flag remains in code and examples.

## Checking action results

Observe before each action. Inspect the fresh screenshot or OCR returned afterward.

- `submission: submitted` means only that events were sent.
- `phone_effect_verified: false` means the client must still verify the phone result.
- If observation fails after submission, the server preserves the submission report and returns `retry_action: false`.

No movement can mean a list boundary, input failure, or observation problem. Do not automatically repeat or reverse an uncertain action. Driver errors or timeouts can also leave partial phone effects.

## Implementation and limits

Taps use target-process SkyLight event records. Keyboard input prepares the mirror's internal activation and receiving-window state before sending target-process events.

a1 scrolling submits two pixel-wheel records through `SLSPostEventRecord`, about 40ms apart. Each record contains the target point. The vertical path does not prime internal activation, switch system foreground, or warp the pointer. The driver stops further submission if it detects a foreground, keyboard focus, or coverage change.

Only the a1 route is published. Other `MIRROR_SCROLL_SCHEME` values are rejected. Hidden, fully covered, minimized, and other-desktop mirrors have not passed scroll acceptance.

SkyLight functions and event layouts are private interfaces that can change across macOS versions. Focus and cursor sampling runs about every 25ms and cannot cover every instant. OCR can merge text or misread icons and emoji.

A per-user file lock serializes this MCP server's instances. It cannot coordinate other drivers, direct CLI calls, or user actions. Cross-machine, cross-version, and long unattended operation remain unverified.

## Tests

```sh
python3 -m unittest -v test_server.py
```

The current suite has 30 offline tests for the protocol, validation, dispatch, and driver guards, including all four signed presets, both axes, and delta construction. They send no phone input. See the [validation record](docs/VALIDATION.md) for device evidence and pending checks.

Experiments, screenshots, videos, model sessions, local environments, and private job-search data are not distributed.

## Acknowledgments and license

The SkyLight event-record implementation draws on [phone-harness](https://github.com/ShawnPana/phone-harness), especially the layout in its `background.py`. Its [MIT copyright notice and license](third_party/phone-harness-LICENSE) are retained. [yabai](https://github.com/koekeishiya/yabai) is an indirect reference for the make-key approach, through phone-harness.

[mirroir-mcp](https://github.com/jfarcand/mirroir-mcp) and [GUIWeave](https://github.com/hyechow/GUIWeave) informed comparison and research. They are not runtime dependencies. This project does not launch them.

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for provenance. This project uses the [MIT license](LICENSE).

The Chinese README is the primary document. This English version follows it.

