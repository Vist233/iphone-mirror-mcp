# Scroll research: 2026-10-26

Persistent background list movement has been demonstrated on one Mac/iPhone setup. The result is intermittent. The packaged MCP driver has not been changed to use this successful research path, and scrolling remains disabled by default.

## Successful route

The local probe used this sequence:

1. Locate the portrait iPhone Mirroring window and confirm Settings is visible.
2. Find an uncovered point inside that window on the current desktop. Refuse input if none exists.
3. Hold the same per-user device transaction lock as the MCP server.
4. Create a pixel-wheel CGEvent with a delta of +50 or -50.
5. Obtain the raw record using `SLEventRecordPointer`.
6. Check the locally observed record length, `0xf8`, and write the target global coordinates at offset `0x10`.
7. Call `SLSPostEventRecord(mainConnection, record, length, 0)`. The local binding supplies four arguments.
8. Post two records per action, with about 40ms between records. Do not capture screenshots inside that loop.
9. Wait about 0.6s, then capture and compare multiple list items. Monitor Mac foreground, keyboard focus and cursor separately.

These are private interfaces and a locally observed memory layout. This is a research recipe, not a portable API contract. A zero return value is not proof of phone movement. The probe did not execute the downloaded GUIWeave binary, move the system pointer, switch the system foreground or automatically reconnect the mirror.

Independent window recording ran alongside the actions. Removing synchronous captures preceded the first measured success, but subsequent failures mean that timing change has not been established as the root cause. Both primed and non-primed actions succeeded, so internal activation is not established as a necessary condition.

## Controlled results

Each delta below is per posted record. Counts are event submissions, not video frames.

| Case | Variant | Measured list result |
| --- | --- | --- |
| 1 | New route: +50, 2 records, no priming | Up by about 10.7% of window height |
| 2 | New route: -50, 2 records, no priming | Down by about 10.7% |
| 3 | New route: -50, 2 records, priming | Down by about 10.7% |
| 4 | New route: +50, 2 records, priming | No clear persistent displacement |
| 5 | New route: -50, 8 records, priming | No clear persistent displacement |
| 6 | New route: +50, 8 records, priming | No clear persistent displacement |
| 7 | New route: +50, 8 records, posting option 1 | No clear persistent displacement |
| 8 | New route: +50, 8 records, AppKit initialization | No clear persistent displacement |
| 9 | Old route: precise wheel phases | No clear persistent displacement |
| 10 | Old route: opposite direction | No clear persistent displacement |
| 11 | Old route: touchpad source identity | No clear persistent displacement |
| 12 | Old route: window-local coordinates | No clear persistent displacement |
| 13 | Old route: complete window record | No clear persistent displacement |
| 14 | Old route: targeted mouse drag | No clear persistent displacement |
| 15 | Old route: window-record mouse drag | No clear persistent displacement |
| 16 | Old route: reconstruct physical wheel fields | No clear persistent displacement |
| 17 | Old route: regular setters for private deltas | No clear persistent displacement |
| 18 | Old route: serialized physical event replay | No clear persistent displacement |
| 19 | Old route: native raw/accelerated delta setters | No clear persistent displacement |
| 20 | Old route: native deltas plus window records | No clear persistent displacement |
| 21 | Old route: temporary mouse receiver window | No clear persistent displacement |

Three additional standalone repetitions of case 1 did not move the list. Replaying cases 1–3 then moved it in cases 2 and 3, by about 10.8% of window height. Case 1 did not move it on that replay. The user confirmed success after both moving sequences.

Across all 27 actions, five produced consistent displacement of multiple list items. All 27 preserved sampled foreground and keyboard focus; 11 preserved sampled pointer position. Two moving actions preserved all three. Other pointer changes have no established cause. Sampling at about 25ms intervals does not establish continuous noninterference. These were ordered, stateful experiments, not independent random trials, so the counts are not a general success-rate estimate.

The summary checks at least two common list items for movement exceeding 2% of window height. This is a research summary rule, not a validated production detector. The fixed Settings title is excluded from the list-movement judgment. Successful before/after images were inspected visually.

## Evidence limits

- The user confirmed no movement in groups 2–4. They did not watch groups 5–6; group 7 has no separate human result. Do not describe all nonmoving trials as human-confirmed failures.
- Seven window recordings are readable, including both successful sequences. Recorders for groups 2–3 exceeded their completion timeout and were terminated; no completed video was retained for those groups. All actions retain before/after captures and event logs locally.
- The full videos have not all been reviewed frame by frame. The reported displacement comes from before/after landmarks and visual checks, supported by the user's observations.
- Some later trials were near a list boundary. Each trial was not reset to an identical middle position. This prevents a clean causal comparison of variants.
- Every successful action used a visible window on the current desktop. Occlusion, hidden windows and other desktops have not passed this route's acceptance gate.
- Private screenshots, videos, physical-event recordings, machine paths and model sessions are not published. The report contains sanitized findings only.

## Integration gate

Reset to a known middle position before each trial. Repeat both directions with the same window visibility and internal state. Compare priming and event cadence one variable at a time. Confirm that recording has actually started and validate its output after every group.

Treat event submission, observed displacement, intended direction and Mac noninterference as separate outcomes. Do not automatically replay an uncertain action. Once the route passes those checks, integrate it behind an explicit experimental option, run it through MCP and verify a Pi/model-driven scroll-and-readback task. Default support requires reliable repeated behavior; that gate has not passed.
