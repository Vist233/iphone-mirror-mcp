# iPhone Mirror MCP

[中文](README.md)

Let an AI client that supports MCP operate your iPhone through Apple's iPhone Mirroring on a Mac.

The project provides screen reading, taps, text input, Home and Spotlight navigation, App Switcher, and vertical and horizontal scroll interfaces. No jailbreak, developer mode, or phone-side runner is required.

It runs locally on the Mac and is not tied to a model or client. It can connect to clients such as Pi and Codex through MCP stdio. Actual Pi calls with a configured DeepSeek Flash provider have been recorded.

> This is an experimental preview, tested on one Mac/iPhone pair. Vertical scrolling has device evidence. Horizontal scrolling and App Switcher are implemented but await device acceptance. Scrolling is off by default. When enabled, it requires an uncovered area of the mirror on the current desktop.

## Capabilities

| Feature | Current status |
| --- | --- |
| Screenshots and local OCR | Tested; no native iPhone UI tree |
| Coordinate and text-based taps | Device evidence exists; inspect the result |
| English, digits, Chinese, and emoji input | Tested; emoji were checked in screenshots |
| Field replacement and explicit Return | Tested; Return can submit content |
| Home and Spotlight | Tested |
| Vertical scrolling (a1) | Device evidence in both directions; off by default |
| Horizontal scrolling and App Switcher | Implemented; device acceptance pending |
| Long press, dragging, and multi-touch | Not supported |

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

## Prerequisites

1. Use a Mac that supports iPhone Mirroring and a paired iPhone.
2. Connect the mirror manually and confirm the phone screen is visible.
3. Keep the iPhone locked.
4. Grant the host application the required Accessibility and screen recording permissions.
5. For scrolling, keep an area of the mirror uncovered on the current desktop.

The user handles connection, authentication, Face ID, and other intervention prompts. Use only one phone driver at a time.

## Installation

Run these commands in the project directory:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
chmod +x mirror-driver
```

The MCP server uses only the Python standard library. The driver requires PyObjC. Pinned versions are in [requirements.txt](requirements.txt).

The launcher uses the project's `.venv/bin/python` by default. Set `MIRROR_PYTHON` to select another interpreter. The launcher does not automatically select a named pyenv environment. Fresh installation on another Mac remains unverified.

## MCP configuration

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

## Tools

| Tool | Arguments and purpose |
| --- | --- |
| `mirror_status` | No arguments; reports window, focus, and scroll configuration |
| `mirror_observe` | OCR by default; optional `image: true` also returns a screenshot |
| `mirror_tap` | Normalized window coordinates `x` and `y`, each in `[0,1)` |
| `mirror_tap_text` | `text` is a substring that must match exactly one OCR item |
| `mirror_navigate` | `destination`: `home`, `spotlight`, or `app_switcher` |
| `mirror_input` | `action: text` with `text`, optional `mode: unicode/ascii` and `replace`; or `action: enter` alone |
| `mirror_scroll` | Exactly one of `direction: up/down/left/right` or legacy `dy: -50/50` |

Version 0.3.0 consolidates five previous navigation and input tools into `mirror_navigate` and `mirror_input`. Refresh the client's tool list after upgrading and update old calls.

Text input uses Unicode by default and supports Chinese and emoji. `mode: ascii` uses physical keycodes for an English keyboard layout. Focus the target field first. `replace: true` replaces its contents. Each call accepts up to 200 characters, rejects control characters, and leaves the clipboard unchanged.

Text input never submits automatically. To press Return, call `mirror_input` separately with `{"action":"enter"}`. Return can submit a search, message, or form. Use it only with an identified target and user authorization.

### Scroll direction

`direction` describes content movement, not finger or wheel movement:

| Argument | Meaning |
| --- | --- |
| `up` | Content moves up to reveal later items; equivalent to `dy: 50` |
| `down` | Content moves down to reveal earlier items; equivalent to `dy: -50` |
| `left` / `right` | Requests content movement left / right; device effect and direction await acceptance |

Each call requests a small fixed step. It does not guarantee 50 pixels or one full screen of movement.

Horizontal scrolling adds a Shift flag to the event without pressing a global Shift key. App Switcher uses Command+2. These controls follow [Apple's documentation](https://support.apple.com/en-us/120421). Their background event paths in this project still await device acceptance.

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

The current suite has 28 offline tests for the protocol, validation, dispatch, and driver guards. They send no phone input. See the [validation record](docs/VALIDATION.md) for device evidence and pending checks.

Experiments, screenshots, videos, model sessions, local environments, and private job-search data are not distributed.

## Acknowledgments and license

The SkyLight event-record implementation draws on [phone-harness](https://github.com/ShawnPana/phone-harness), especially the layout in its `background.py`. Its [MIT copyright notice and license](third_party/phone-harness-LICENSE) are retained. [yabai](https://github.com/koekeishiya/yabai) is an indirect reference for the make-key approach, through phone-harness.

[mirroir-mcp](https://github.com/jfarcand/mirroir-mcp) and [GUIWeave](https://github.com/hyechow/GUIWeave) informed comparison and research. They are not runtime dependencies. This project does not launch them.

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for provenance. This project uses the [MIT license](LICENSE).

The Chinese README is the primary document. This English version follows it.

