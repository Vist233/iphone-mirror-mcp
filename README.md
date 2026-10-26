# iPhone Mirror MCP — experimental preview

Control a paired iPhone through Apple's iPhone Mirroring from an MCP client. The driver runs on the Mac. No model API or Codex dependency is required.

**This is a preview with limited device validation. Background scrolling has not passed validation and is disabled by default.** Several tested actions preserved the sampled Mac foreground, keyboard focus and cursor position. This does not guarantee uninterrupted desktop use on every OS, application or task.

## Status

| Capability | Evidence |
| --- | --- |
| Window capture and local OCR | Tested on one Mac/iPhone setup |
| Tap, Home, Spotlight, opening Chrome | Tested on selected system and browser screens |
| English, digits, Chinese, emoji and text replacement | Tested; emoji checked in screenshots |
| Return for browser navigation | Tested on a public example page |
| Pi + configured DeepSeek Flash provider | Real MCP calls and text readback tested |
| Background scroll | Not validated; disabled |
| Long press, drag, multi-touch, arbitrary apps | Not supported as verified features |
| Other Macs and long unattended workflows | Not validated |

Device evidence was collected on 2026-10-24 with macOS 27.0.1 and iPhone Mirroring 2.0. Protocol tests can run without a phone. See [validation](docs/VALIDATION.md) for the distinction.

On 2026-10-26, this prepared preview also passed a core device regression: Settings navigation, three text replacements, Home/Spotlight, disconnect refusal and submission reporting after an injected observation failure. This does not validate background scrolling or other Macs.

## Setup

Use a Mac that already supports iPhone Mirroring with your iPhone. Connect the mirror manually and confirm the phone screen is visible. Keep the iPhone locked while using Apple's mirror. The host that runs this driver needs the relevant Accessibility and screen recording permissions. Connection and authentication prompts require the user.

Create a dedicated environment in the repository:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
chmod +x mirror-driver
```

The launcher uses `.venv/bin/python`, or the executable path in `MIRROR_PYTHON`. It does not select a named pyenv environment. The protocol server itself uses only the Python standard library; the driver requires PyObjC. Installation on a second Mac remains unverified.

## MCP configuration

Replace the paths with your checkout and Python interpreter:

```json
{
  "mcpServers": {
    "iphone-local": {
      "command": "/absolute/path/iphone-mirror-mcp/.venv/bin/python",
      "args": ["/absolute/path/iphone-mirror-mcp/server.py"],
      "env": {
        "MIRROR_PYTHON": "/absolute/path/iphone-mirror-mcp/.venv/bin/python"
      }
    }
  }
}
```

For Pi, place this configuration in the project's `.pi/mcp.json` and inspect `pi mcp list --json`. Pi's built-in MCP extension must be enabled. If using `--no-extensions`, explicitly include `--extension builtin:mcp`. Avoid running another phone driver at the same time.

## Tools

| Tool | Arguments |
| --- | --- |
| `mirror_status` | None; read window and focus information |
| `mirror_observe` | Optional `image: true`; OCR is the default |
| `mirror_tap` | `x`, `y`: normalized window coordinates, each in `[0,1)` |
| `mirror_tap_text` | `text`: must match exactly one OCR item by substring |
| `mirror_home` | None |
| `mirror_spotlight` | None |
| `mirror_type_ascii` | `text`, optional `replace`; physical English-layout keys |
| `mirror_type` | Unicode `text`, optional `replace` |
| `mirror_key` | `key`: `return` or `enter` |
| `mirror_scroll` | Experimental `dy`; rejected by the driver by default |

Observe the screen before each action. Inspect the fresh observation after it. `submission: submitted` means the event was sent, while `phone_effect_verified: false` means the client must check the phone result.

If an action was submitted but its next observation fails, the server preserves the submission report and returns `retry_action: false`. Observe again before deciding whether to repeat the action. A timeout or driver failure can also leave the phone effect uncertain; an error alone is not permission to retry an action that could submit or delete data.

Typing is limited to 200 characters and rejects control characters. It does not implicitly press Return or change the clipboard. `replace: true` replaces the current field, so verify the field first. Return may submit a message or form; use it only for a user-authorized submission.

## Implementation and limits

The driver captures the mirror window and runs Apple Vision OCR locally. Pointing uses target-process SkyLight records. Keyboard input uses target-process events after preparing the mirror's internal activation and receiving-window state. The default path contains no system foreground-switch or pointer-warp fallback.

SkyLight entry points and event layouts are private interfaces. They can change between macOS releases. Focus and cursor measurements occur at 25ms intervals during input. They describe sample times, not every instant. OCR can merge icons with text or misread emoji. There is no native iPhone accessibility tree in this implementation.

A per-user file lock serializes transactions between copies of this server. It does not coordinate other drivers, the user, or direct CLI calls. No phone-side helper, developer mode, jailbreak or system protection changes were used for the recorded device tests.

`MIRROR_ENABLE_EXPERIMENTAL_INPUT=1` enables research routes in the driver. These routes are unverified and are not part of the preview's usable capability claim. They never automatically fall back to foreground input.

## Test and contribute

```sh
python3 -m unittest -v test_server.py
```

See [the validation and release gates](docs/VALIDATION.md). Keep screenshots, local client configurations, model sessions and credentials out of contributions. See [acknowledgments](THIRD_PARTY_NOTICES.md). Distributed under the [MIT license](LICENSE).
