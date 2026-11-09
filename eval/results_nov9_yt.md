# Agent eval — nov9_yt

2026-11-09 15:25 · CPH2491 (Android 16) · planner jev · LLM openai/gpt-oss-120b (reasoning low) · commit uncommitted · STT transcripts: default (te,hi,en auto-detect)

Input: the user's 24 recorded clips (12 commands × Telugu/Hindi), transcribed once by Gnani Prisma (`eval/stt_results.md`), each transcript replayed 3× on the real phone. Success = harness predicate on the live screen after the run. Dry-run tasks stop before the commit tap (alarm Done, timer Start, Call, Send); sending/calling is disabled entirely (user rule). STT errors are included: a misheard clip counts as a fail.

**Overall: 4/6 (67%)** · median wall 6.4 s

| split | pass | median s |
|---|---|---|
| Telugu | 3/3 (100%) | 9.1 |
| Hindi | 1/3 (33%) | 2.3 |
| routed to a deterministic handler / safety block | 4/6 (67%) | 6.4 |
| routed to the LLM agent loop | - | - |

| task | te | hi | median s | routes seen | failure reasons |
|---|---|---|---|---|---|
| youtube_devotional | 3/3 (100%) | 1/3 (33%) | 6.4 | open_app, youtube_search | hi: done / yt query '' |
