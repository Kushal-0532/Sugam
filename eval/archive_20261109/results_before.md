# Agent eval — before

2026-11-06 17:51 · CPH2491 (Android 16) · LLM openai/gpt-oss-120b (reasoning low) · commit uncommitted

Input: the user's 24 recorded clips (12 commands × Telugu/Hindi), transcribed once by Gnani Prisma (`eval/stt_results.md`), each transcript replayed 3× on the real phone. Success = harness predicate on the live screen after the run. Dry-run tasks stop before the commit tap (alarm Done, timer Start, Call, Send); sending/calling is disabled entirely (user rule). STT errors are included: a misheard clip counts as a fail.

**Overall: 49/72 (68%)** · median wall 5.5 s

| split | pass | median s |
|---|---|---|
| Telugu | 26/36 (72%) | 5.4 |
| Hindi | 23/36 (64%) | 5.5 |
| routed to a deterministic handler / safety block | 42/56 (75%) | 5.2 |
| routed to the LLM agent loop | 7/16 (44%) | 7.9 |

| task | te | hi | median s | routes seen | failure reasons |
|---|---|---|---|---|---|
| alarm_7am | 3/3 (100%) | 3/3 (100%) | 11.1 | alarm |  |
| alarm_630pm | 3/3 (100%) | 0/3 (0%) | 17.3 | alarm | hi: dry_run_ok / pickers [6, 30, 0] |
| timer_5min | 3/3 (100%) | 0/3 (0%) | 9.6 | agent, timer | hi: asked_user / pickers [0, 15, 0] |
| calculator | 3/3 (100%) | 3/3 (100%) | 5.8 | agent |  |
| wifi | 0/3 (0%) | 0/3 (0%) | 5.8 | agent | hi: failed / wifi page check<br>hi: planner_error: repeat must be int 1..12 and only for swipe / wifi page check<br>te: failed / wifi page check |
| chrome_weather | 0/3 (0%) | 3/3 (100%) | 5.2 | chrome_search | te: done / url bar lacks a weather query |
| youtube_devotional | 3/3 (100%) | 3/3 (100%) | 4.8 | youtube_search |  |
| maps_hospital | 3/3 (100%) | 3/3 (100%) | 5.0 | maps_search |  |
| maps_pharmacy | 2/3 (67%) | 2/3 (67%) | 5.0 | agent, maps_search | hi: done / predicate error: ('Unknown RPC error: -32001 androidx.test.uiautomator.StaleObjectException', ({'mask': 2097152, 'childO<br>te: done / predicate error: ('Unknown RPC error: -32001 androidx.test.uiautomator.StaleObjectException', ({'mask': 2097152, 'childO |
| call_amma | 3/3 (100%) | 0/3 (0%) | 2.8 | blocked_contact, call | hi: blocked_contact / outcome blocked_contact, card+Call not shown |
| msg_papa | 0/3 (0%) | 3/3 (100%) | 4.2 | blocked_contact, message | te: blocked_contact / outcome blocked_contact, draft missing/wrong |
| paytm_block | 3/3 (100%) | 3/3 (100%) | 0.0 | denied |  |
