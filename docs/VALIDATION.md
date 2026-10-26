# Validation and release gates

## Existing evidence

On 2026-10-24, one Mac/iPhone setup completed capture, OCR, taps, Home/Spotlight, English/Chinese input and browser navigation. Pi with a configured DeepSeek Flash provider made actual MCP calls and read back the results.

For selected successful inputs, every focus/cursor sample was unchanged: 43 samples for direct MCP English input, 41 for model-driven English input, 27 for model-driven Chinese input, and 18 for opening Chrome. Sampling ran at about 25ms intervals. Other trials contained focus or pointer changes and were not counted as passing noninterference.

Sixteen scroll trials covered phases, coordinates, source identity, complete records, drag, directions, desktop placement, serialization replay, raw deltas and mouse-target routing. No repeatable background scroll passed. One small movement did not reproduce. Scroll remains disabled.

Those are the initial device results. On 2026-10-26, the prepared preview completed another device regression: Settings navigation, OCR targeting, three exact text replacements, Home and Spotlight. English input had 42 unchanged focus/cursor samples, Chinese plus emoji 28, and mixed-case digits 25. Emoji were checked in an image. Pointing trials with cursor changes were kept separate.

A real Home action followed by an injected read failure preserved the submission report and returned `retry_action: false`; the wrapper recorded exactly one Home and one read attempt. Normal observation then confirmed the home screen. A real iPhone-in-use state also refused input before submission; the user restored the connection manually. No new model run was performed, so Pi/Flash evidence remains dated 2026-10-24.

Raw screenshots and model sessions are excluded from this public preview because they contain personal information. Fresh dependency installation, a second Mac and long unattended workflows remain unverified.

## Checks the maintainer can run without the phone

- Protocol version negotiation, notification handling and recovery after malformed JSON.
- Argument rejection before driver input, including invalid coordinates, control characters and unsupported keys.
- Ambiguous OCR text must not trigger a click.
- A held cross-process device lock must prevent driver invocation.
- Unicode event chunking must preserve surrogate pairs.
- A submitted action must remain identifiable when the following observation fails.
- The launcher must preserve arguments and work without a named pyenv environment.
- The exported archive must exclude local configurations, environments, captures and model session logs.

The current suite has 14 tests. They test protocol behavior and selected boundaries, not actual phone input.

## Device checks before calling it a validated release

1. Confirm the mirror is connected and another Mac application is foreground. Use only Settings or a disposable test field.
2. Test Home, Spotlight, opening Settings, tapping a field, replacing ASCII, replacing Chinese and emoji, and reading the exact result. Do not send a message or application.
3. Record the foreground process, keyboard-focus process and pointer throughout each action. Review unexpected changes separately from phone success.
4. Repeat with the mirror on the same desktop, occluded, and on another desktop. Confirm captured frames reflect the current phone state.
5. Test a disconnected mirror. The driver must refuse input and must not reconnect or switch foreground automatically.
6. Test the new observation-failure report on the phone: an already-submitted action must not be repeated automatically.
7. Install into a fresh environment and verify from a clean checkout. Repeat on another Mac before claiming cross-machine support.

## Scroll research: separate acceptance gate

GUIWeave's public `mirror_daemon` binary uses a different raw-record posting route, `SLSPostEventRecord`. The downloaded binary was not run. On 2026-10-26, a separate bounded probe explicitly supplied the locally observed fourth argument and tested eight combinations of directions, frame counts, internal activation, posting options and Cocoa initialization. The user reported seeing the iPhone Settings list scroll upward, but captured landmarks did not establish repeatable persistent displacement. Neither complete failure nor supported scrolling has been demonstrated. Production scrolling remains disabled.

Keep this research separate from the preview's verified input paths. If the route works, require repeated up/down page movement with stable Mac focus and pointer before exposing it as supported MCP scrolling. Then run the same action through Pi and inspect the phone result. Do not distribute the downloaded candidate binary as part of this preview.

## Release wording

This experimental preview is shared with the limits above visible. A stable, zero-interference or fully autonomous phone-control claim requires more device evidence. The project uses the MIT license; research routes remain outside the verified capability claim.
