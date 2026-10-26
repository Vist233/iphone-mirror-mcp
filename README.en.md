# iPhone Mirror MCP

[中文](README.md)

**iPhone Mirror MCP** is a local MCP (Model Context Protocol) server that lets MCP-capable AI clients such as Claude Code, Codex and Pi read and operate an iPhone screen through macOS iPhone Mirroring. There is a real call record of Pi with DeepSeek Flash driving it.

The usual approach brings the mirror window to the foreground or moves the system pointer before posting events. This project does not: clicks, text input and navigation target the mirror process or window directly, without switching the system foreground, changing keyboard focus or moving the mouse.

The conditions are equally explicit: before input it takes a local screenshot and uses Apple Vision OCR to judge the page state; **scrolling requires the mirror window to be visible on the current desktop with at least one area not covered by other windows** (it does not have to be the frontmost window). No jailbreak, developer mode or phone-side app is required.

> Experimental preview: vertical scrolling has device evidence; horizontal movement is confirmed by the user, and exact left/right mapping is still being checked; App Switcher awaits device acceptance. Scrolling is available by default but still subject to the visibility check.

## Quick start

Send this line to your AI agent:

> [!TIP]
> Set up https://github.com/Vist233/iphone-mirror-mcp so I can use it to control my iPhone.

A person does two things: grant permissions (see [Required permissions](#required-permissions)), and connect iPhone Mirroring with the iPhone locked. The rest is the agent's job.

## Required permissions

In macOS System Settings → Privacy & Security, enable these for the program that actually launches the tool:

| Permission | Purpose |
| --- | --- |
| Screen Recording / Screen & System Audio Recording | Capture the iPhone Mirroring window for OCR and image observation; no audio is captured |
| Accessibility / related device-control permission | Read the mirror's accessibility state and post clicks, keyboard and wheel events |

Pane names vary by macOS version and language. If you launch from Terminal or iTerm, check that terminal; if Codex or another MCP client launches it, check that client. Trust the responsible program named by macOS — granting only "iPhone Mirroring" is not enough.

After changing permissions, quit and reopen the host program when macOS asks. The driver checks input-event posting permission, but `trusted_post_event` in `info` is not a full permission diagnosis; confirm capture and OCR with one `read` call.

The published code does not listen to global keyboard or wheel input, so Input Monitoring is not a runtime requirement; Full Disk Access, Microphone and Apple Events automation are not required either. Connection, authentication and Face ID prompts remain user actions.

Entry points for the relevant panes: Apple's [Accessibility](https://support.apple.com/en-euro/guide/mac-help/mh43185/27/mac/27) and [Screen Recording](https://support.apple.com/en-gb/guide/mac-help/mchl592e5686/mac) guides.

## Usage conditions

1. iPhone Mirroring is connected and the iPhone stays locked.
2. When scrolling, the mirror window must be exposed: on the current desktop, with at least one area not covered by other windows; it does not need to be the frontmost app.

Why these conditions exist and what to do when an action fails is covered in [the detailed guide for AI](#detailed-guide-for-ai).

## Data and privacy: what leaves your Mac

The project itself makes no network requests: no model API, account or API key, and no telemetry, crash reporting or analytics SDK. The following is handed to the MCP client that calls it:

| Content | Source | Notes |
| --- | --- | --- |
| OCR text rows | `mirror_observe` | Screen text, confidence, normalized coordinates |
| Screenshot | `mirror_observe` with `image: true` | PNG, base64 encoded |
| Window and focus metadata | `mirror_status`, action results | Window ID and size, foreground and background PIDs, keyboard focus, cursor position, input permission state |

- If the client uses a cloud model, this content is sent to the model service like any other conversation; whether and where it is uploaded depends on the client and your configuration. This project neither participates in nor records that.
- Screenshots are written to disk in only two places: the CLI `read` and `capture` commands write to the path the caller gives; the MCP path uses a temporary directory and deletes the file when the OCR call returns, so it does not persist.
- OCR reads all visible text on the screen, which may include private messages, verification codes or notifications. Confirm the client's data handling before connecting.
- The project does not read the clipboard, capture audio, listen to global keyboard or wheel input, or touch Photos and notifications.

## How it works

```text
AI / MCP client
    ↓ MCP stdio
iphone_mirror_mcp.server   argument validation, device lock, tool dispatch, post-action observation
    ↓ starts the driver process
iphone_mirror_mcp.driver   capture, Vision OCR, click, keyboard and wheel events
    ↓
iPhone Mirroring on the Mac
    ↓ Apple handles the connection and interaction transport
iPhone
```

The driver operates the mirror on the Mac; it does not speak the iPhone control protocol directly. Reading the screen uses local capture and Apple Vision OCR. No model API is needed at runtime.

## Detailed guide for AI

People only need the two conditions above. The agent reads [AGENTS.md](AGENTS.md) on demand: installation, wiring, tool arguments, plus permission failures, visibility rules, partial submission and retry rules.

## Tools

| Tool | Arguments and purpose |
| --- | --- |
| `mirror_status` | No arguments; reports window, focus and scroll capability configuration |
| `mirror_observe` | OCR by default; optional `image: true` also returns a screenshot |
| `mirror_tap` | Normalized window coordinates `x` and `y`, each in `[0,1)` |
| `mirror_tap_text` | `text` is a substring that must match exactly one OCR item |
| `mirror_navigate` | `destination`: `home`, `spotlight` or `app_switcher` |
| `mirror_input` | `action: text` with `text`, optional `mode: unicode/ascii` and `replace`; or `action: enter` alone |
| `mirror_scroll` | `direction: up/down/left/right`, optional `magnitude: 20/50/100/200` (default 50); or the legacy vertical-only `dy` |

Parameter details, CLI commands and scroll presets are in [AGENTS.md](AGENTS.md).

## FAQ

### Is granting permissions mandatory? What happens without them?

Yes, mandatory. Without Screen Recording the driver cannot capture or OCR and refuses before sending any input; without Accessibility, clicks, keyboard and wheel events cannot be posted. Grant permissions to the program that actually launches the tool (the terminal or MCP client) — granting only "iPhone Mirroring" does nothing. Restart the host program after changing them.

### Does it take over the foreground or move my mouse?

No. The driver does not use global `CGEventPost`, does not warp the pointer, and does not bring the mirror to the system foreground; clicks, keyboard and scrolling are posted to the mirror process or window. Results expose `focus_unchanged`, `cursor_same_at_samples` and 25 ms sampling records for checking. Boundaries are in [the detailed guide for AI](#detailed-guide-for-ai): sampling cannot cover every instant, some earlier trials did contain pointer changes, and cross-app, cross-version behavior remains unverified.

### Why does scrolling require a visible window when tapping does not?

WindowServer hit-tests scroll events against the target point inside the event record; with no visible point belonging to the mirror there is nowhere to deliver them, so the driver checks first and reports an error instead of sending the event to another window. Clicks and keyboard input go directly to the mirror process and do not depend on that hit test.

### Does it require jailbreak, developer mode or a phone-side app?

No. The project uses only Apple's built-in iPhone Mirroring on the Mac and local PyObjC. Nothing is installed on the iPhone.

### Does it work on Windows or Linux? Can I use it without a Mac?

No. The implementation depends on macOS private SkyLight interfaces and iPhone Mirroring, with no cross-platform path.

### Which AI clients are supported?

Any MCP stdio client, such as Claude Code, Codex or Pi. Actual calls with Pi and a DeepSeek Flash provider have been recorded; wiring is in [AGENTS.md](AGENTS.md) and the agent does it.

### Does it upload my screen content to the cloud?

The project does not use the network itself. OCR text, optional screenshots and window metadata are handed to the MCP client; if the client uses a cloud model, that content is sent with the conversation, as determined by the client and your configuration. On the MCP path, screenshots exist only in a temporary directory and are deleted after OCR.

### Does it support long press, drag or multi-touch? What if scrolling does not move?

Long press, dragging and multi-touch are not supported. No movement can mean a list boundary, an input failure or an observation problem. Do not automatically repeat or reverse an uncertain action; observe first.

### Is it free? Can it run unattended?

It is MIT licensed and free to use and modify. This is an experimental preview validated on one Mac/iPhone pair; cross-machine, cross-version and long unattended operation remain unverified.

## Validation and limits

Validated on one Mac/iPhone pair; focus and cursor sampling runs about every 25 ms and cannot cover every instant. Cross-machine, cross-version and long unattended operation remain unverified. Experimental files, screenshots, recordings, model sessions and local runtime environments are not distributed.

## Acknowledgments and license

The SkyLight event-record implementation draws on [phone-harness](https://github.com/ShawnPana/phone-harness), especially the layout in its `background.py`; its MIT notice and license are reproduced at the end of [LICENSE](LICENSE). [yabai](https://github.com/koekeishiya/yabai) is an indirect reference for the make-key approach, through phone-harness.

[mirroir-mcp](https://github.com/jfarcand/mirroir-mcp) and [GUIWeave](https://github.com/hyechow/GUIWeave) informed comparison and research. They are not runtime dependencies. This project does not launch them.

Third-party sources and the full license text are in [LICENSE](LICENSE).

The Chinese README is the primary document. This English version follows it.
