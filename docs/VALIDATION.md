# Validation and release gates

## Scope

Tests used one Mac/iPhone pair, macOS 27.0.1 and iPhone Mirroring 2.0. Results do not establish cross-machine or cross-version support. This revision publishes only the `a1` scroll route. Other schemes and raw experiments remain local.

## Core device evidence

On 2026-10-24, capture, OCR, taps, Home/Spotlight, English/Chinese input and browser navigation were exercised. Pi with a configured DeepSeek Flash provider made actual MCP calls and read back text.

On 2026-10-26, a core regression covered Settings navigation, three text replacements, Home/Spotlight, refusal during a real iPhone-in-use state and submission reporting after an injected observation failure. The three input trials had 42, 28 and 25 unchanged focus/cursor samples. Emoji were checked visually. The injected failure followed one real Home action; the wrapper recorded exactly one Home and one read attempt, and the response discouraged replay.

Sampling ran at about 25ms intervals. Other pointing trials contained cursor changes and were not counted as noninterference passes. These historical core results were not repeated as a new Pi/model run for this revision.

## a1 scroll evidence

The measured route posts two bare pixel-wheel records through `SLSPostEventRecord` with a target global point written into each record. It uses no internal-activation priming. The default scheme has no phase flags or private-delta setters.

The saved controlled Settings matrix contains six `a1` actions: three in each direction. All six showed persistent movement of multiple text rows; all six preserved sampled foreground/keyboard focus and five preserved sampled cursor position. Typical movement was about 0.107 of window height, not one full screen.

Across the saved exploratory and matrix summaries, 33 `a1` requests used exactly +/-50: 27 had measured movement and six did not. Boundary effects were suspected for the six, but they must not be removed to advertise a 100% general success rate. A larger-magnitude trial also moved, so the study does not prove a hard magnitude ceiling. The API accepts only the two repeatedly measured presets, -50 and 50.

Raw experiment files and OCR landmarks contain personal data and are not part of this repository. The aggregate counts above were recomputed from those local summaries. No return value provides a phone-side acknowledgement; callers must compare observations.

## Current revision checks

The offline suite has 22 tests. In addition to protocol and transaction checks, it executes the real driver functions with isolated backends to check that a1 does not prime/deactivate the mirror, rejects unmeasured magnitudes and unpublished schemes before input, requires explicit opt-in, posts two records, and stops before posting on focus/coverage changes. These are not phone-effect tests.

A fresh MCP scroll regression and exact-source hashes are recorded privately by the maintainer before publication. Only observed results from that regression should be reported as current-revision device checks.

## Remaining gates

- Inspect exact row displacement and direction after each action. Treat no movement as ambiguous; do not retry automatically.
- Validate installation on another Mac, additional applications and longer workflows before broader claims.
- Hidden, fully occluded, minimized and other-desktop mirrors have not passed this route's acceptance gate. A suitable uncovered point is required by the implementation.
- Reconnection, authentication, Face ID and user-intervention prompts remain user actions.
- Fresh dependency installation, cross-version support and long unattended operation remain unverified.

This remains an MIT experimental preview. Stable, zero-interference or fully autonomous phone-control claims require further evidence.
