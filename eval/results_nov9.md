# Agent eval — nov9

2026-11-09 14:52 · CPH2491 (Android 16) · planner jev · LLM openai/gpt-oss-120b (reasoning low) · commit uncommitted · STT transcripts: default (te,hi,en auto-detect)

Input: the user's 24 recorded clips (12 commands × Telugu/Hindi), transcribed once by Gnani Prisma (`eval/stt_results.md`), each transcript replayed 3× on the real phone. Success = harness predicate on the live screen after the run. Dry-run tasks stop before the commit tap (alarm Done, timer Start, Call, Send); sending/calling is disabled entirely (user rule). STT errors are included: a misheard clip counts as a fail.

**Overall: 49/72 (68%)** · median wall 8.0 s

| split | pass | median s |
|---|---|---|
| Telugu | 24/36 (67%) | 6.7 |
| Hindi | 25/36 (69%) | 10.1 |
| routed to a deterministic handler / safety block | 46/57 (81%) | 6.5 |
| routed to the LLM agent loop | 3/15 (20%) | 22.2 |

| task | te | hi | median s | routes seen | failure reasons |
|---|---|---|---|---|---|
| alarm_7am | 3/3 (100%) | 3/3 (100%) | 14.2 | alarm |  |
| alarm_630pm | 3/3 (100%) | 3/3 (100%) | 13.2 | alarm |  |
| timer_5min | 3/3 (100%) | 0/3 (0%) | 17.1 | agent, timer | hi: done / pickers None |
| calculator | 3/3 (100%) | 3/3 (100%) | 2.0 | open_app |  |
| wifi | 0/3 (0%) | 0/3 (0%) | 17.6 | agent | hi: asked_user / wifi page check<br>hi: stuck_loop / wifi page check<br>te: done / wifi page check |
| chrome_weather | 0/3 (0%) | 3/3 (100%) | 7.0 | chrome_search | te: done / url bar lacks a weather query |
| youtube_devotional | 0/3 (0%) | 1/3 (33%) | 7.3 | open_app, youtube_search | hi: done / yt query ''<br>te: done / yt query '' |
| maps_hospital | 3/3 (100%) | 3/3 (100%) | 6.0 | maps_search |  |
| maps_pharmacy | 3/3 (100%) | 3/3 (100%) | 14.4 | agent, maps_search |  |
| call_amma | 3/3 (100%) | 0/3 (0%) | 7.8 | agent, call | hi: asked_user / outcome asked_user, card+Call not shown<br>hi: dry_run_ok / outcome dry_run_ok, card+Call not shown |
| msg_papa | 0/3 (0%) | 3/3 (100%) | 5.4 | blocked_contact, message | te: blocked_contact / outcome blocked_contact, draft missing/wrong |
| paytm_block | 3/3 (100%) | 3/3 (100%) | 0.0 | denied |  |

Agent-loop runs: 15 · steps jev 24 / groq 40 · mean steps per run 4.3 · planner seconds per step 1.96 · median planner s per run 7.8

## Addendum (Nov 9, after the run above)
`youtube_devotional` was re-run alone (`--tag nov9_yt`, `eval/results_nov9_yt.md`) after the harness predicate was corrected: "play ..." commands now tap the first video, so a pass is an open YouTube player (`watch_player`), not the results page. Result **4/6**: Telugu 3/3, Hindi 1/3 (two runs mis-heard by Prisma, route `open_app`). With that task replaced, the clip total is **52/72 (72%)**. The 49/72 above is the unmodified run.
