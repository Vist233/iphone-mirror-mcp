# Validation and release gates

## Existing evidence

On 2026-10-24, one Mac/iPhone setup completed capture, OCR, taps, Home/Spotlight, English/Chinese input and browser navigation. Pi with a configured DeepSeek Flash provider made actual MCP calls and read back the results.

For selected successful inputs, every focus/cursor sample was unchanged: 43 samples for direct MCP English input, 41 for model-driven English input, 27 for model-driven Chinese input, and 18 for opening Chrome. Sampling ran at about 25ms intervals. Other trials contained focus or pointer changes and were not counted as passing noninterference.

Sixteen scroll trials covered phases, coordinates, source identity, complete records, drag, directions, desktop placement, serialization replay, raw deltas and mouse-target routing. In that initial round, no repeatable background scroll passed. One small movement did not reproduce. Later results are recorded below; default MCP scrolling remains disabled.

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

GUIWeave's public `mirror_daemon` binary uses `SLSPostEventRecord`. The downloaded binary was not run. A separate local probe explicitly supplied the fourth argument observed in the local system implementation.

An initial eight-case round had a human report of upward Settings movement without measured persistent displacement. A later 21-case comparison, plus six retests, established persistent displacement in five actions. The user confirmed success twice. Two of those actions also preserved every sampled Mac foreground, keyboard-focus and cursor value. These findings supersede the earlier absence of measured displacement; they do not establish reliable scrolling.

The successful route used two pixel-wheel records of +50 or -50, with global coordinates written into the raw record, posted through the main WindowServer connection. In the first sequence, all three actions moved the list; replaying the sequence moved it in the two negative-direction actions. Three standalone positive-direction retests did not move it. Priming and non-priming variants both succeeded. No synchronous capture ran inside the posting loop.

See [the detailed research summary](SCROLL_RESEARCH.md) for all variants, recording gaps and acceptance gates. The successful probe is separate from the packaged MCP driver. The existing experimental-input flag does not switch to this new route. Default MCP scrolling remains disabled. Require controlled, repeated movement in both directions and separate focus/pointer checks before integrating it. Then verify an actual Pi/model call. No research binary or private captures are distributed.

## Release wording

This experimental preview is shared with the limits above visible. A stable, zero-interference or fully autonomous phone-control claim requires more device evidence. The project uses the MIT license; research routes remain outside the verified capability claim.
