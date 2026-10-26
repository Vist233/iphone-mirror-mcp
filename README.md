# iPhone Mirror MCP — experimental preview

Control a paired iPhone through Apple's iPhone Mirroring from an MCP client. The driver runs on the Mac. It requires no model API, Codex dependency, phone-side runner, jailbreak or developer mode.

**Limited device validation: one Mac/iPhone pair.** The core tools have device evidence, and this revision integrates the measured `a1` background scroll route. Scrolling requires explicit opt-in and an uncovered point inside the mirror window on the current desktop. Other Macs, hidden windows and long unattended workflows remain unverified.

## Capabilities

| Capability | Evidence and limits |
| --- | --- |
| Window capture and local OCR | Tested on one setup; no native iPhone UI tree |
| Tap, Home, Spotlight and opening Chrome | Tested on selected system and browser screens |
| English, digits, Chinese, emoji and replacement | Tested; emoji checked in screenshots |
| Return for browser navigation | Tested on a public example page; may submit data in other contexts |
| Pi + configured DeepSeek Flash provider | Actual MCP calls and text readback tested |
| Background scroll (`a1`) | Measured bounded steps in both directions on Settings; off by default |
| Long press, dragging and multi-touch | Not supported as verified features |

Selected successful actions preserved sampled Mac foreground, keyboard focus and cursor position. Other trials contained changes. Sampling is not a guarantee of uninterrupted desktop use on every application or OS build. See [validation](docs/VALIDATION.md).

## Setup

Use a Mac that already supports iPhone Mirroring. Connect it manually and confirm the phone screen is visible. Keep the iPhone locked. The host needs Accessibility and screen recording permissions. Connection and authentication prompts require the user.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
chmod +x mirror-driver
```

The launcher uses `.venv/bin/python`, or the executable specified by `MIRROR_PYTHON`. It does not select a named pyenv environment. The protocol server uses only the Python standard library; the driver requires PyObjC. Fresh installation on another Mac remains unverified.

## MCP configuration

Replace all paths with your checkout. This example explicitly enables experimental `a1` scrolling; omit `MIRROR_ENABLE_EXPERIMENTAL_INPUT` to leave scrolling disabled.

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

For Pi, put the configuration in the project's `.pi/mcp.json` and inspect `pi mcp list --json`. Pi's built-in MCP extension must be enabled. With `--no-extensions`, explicitly include `--extension builtin:mcp`. Use only one phone driver at a time.

## Tools

| Tool | Arguments |
| --- | --- |
| `mirror_status` | None; report window, focus and configured scroll capability |
| `mirror_observe` | Optional `image: true`; text OCR is the default |
| `mirror_tap` | Normalized `x`, `y`, each in `[0,1)` |
| `mirror_tap_text` | `text`; must match exactly one OCR item by substring |
| `mirror_navigate` | `destination`: `home`, `spotlight`, or `app_switcher` (recent apps) |
| `mirror_input` | `action: text` with `text`, optional `mode: unicode` (default) or `ascii`, optional `replace`; or `action: enter` alone |
| `mirror_scroll` | Exactly one of `direction: up/down/left/right` or legacy `dy: -50/50` |

Version 0.3.0 consolidates the five old navigation/input tools into `mirror_navigate` and `mirror_input`. Clients must refresh their tool list and update old calls. Text input never implicitly submits. Submitting requires a separate `mirror_input({"action":"enter"})` call.

`direction` describes content movement: `up` is `dy: 50`, `down` is `dy: -50`. Left/right use the same records with the Shift modifier flag, without pressing a global Shift key. [Apple documents Shift+scroll for horizontal swipes and Command+2 for App Switcher](https://support.apple.com/en-us/120421). Their background injection is implemented but has not passed device acceptance; verify the returned screen and direction.

On the tested `a1` setup, positive `dy` moves content upward to reveal later items; negative moves content downward to reveal earlier items. The argument is a tested preset, not a guaranteed pixel distance or one full screen. Small steps may be needed to inspect a long list.

Observe before each action and inspect the fresh observation returned afterward. `submission: submitted` means events were sent. `phone_effect_verified: false` means the client still needs to verify the phone result. No movement is ambiguous: a boundary, input failure or observation problem can cause it. Do not automatically repeat or reverse an uncertain action.

If an already-submitted action's next observation fails, the server preserves its submission report and returns `retry_action: false`. Observe again before deciding what to do. Driver errors and timeouts can also leave partial phone effects.

Typing is limited to 200 characters, rejects control characters, and does not implicitly press Return or change the clipboard. `replace: true` replaces the current field. Return may submit a message or form; use it only for an authorized submission.

## Implementation and limits

Capture and Vision OCR run locally. Taps use target-process SkyLight records. Keyboard input uses target-process events after preparing the mirror's internal activation and receiving-window state.

`a1` scrolling posts two bare pixel-wheel records through `SLSPostEventRecord`, about 40ms apart, with the target point in each raw record. It does not prime internal activation, switch system foreground or warp the pointer. Posting stops if the sampled Mac foreground/keyboard focus or target coverage changes. Only `a1` is published; selecting another `MIRROR_SCROLL_SCHEME` is rejected.

SkyLight functions and record layouts are private interfaces that can change between macOS versions. Input sampling runs at about 25ms intervals, not continuously. OCR can merge icons or misread emoji. A per-user file lock serializes copies of this MCP server but cannot coordinate other drivers, direct CLI calls or the user.

## Tests and provenance

```sh
python3 -m unittest -v test_server.py
```

The offline suite checks protocol behavior and driver guards without sending phone input. See [device validation](docs/VALIDATION.md). Experiments, screenshots, videos, model sessions, local environments and job-search data are not distributed. See [acknowledgments](THIRD_PARTY_NOTICES.md) and the [MIT license](LICENSE).
