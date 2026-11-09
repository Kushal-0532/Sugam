# Agent eval — agent_jev

2026-11-06 19:20 · CPH2491 (Android 16) · planner jev · LLM openai/gpt-oss-120b (reasoning low) · commit uncommitted · STT transcripts: default (te,hi,en auto-detect)

Input: the user's 24 recorded clips (12 commands × Telugu/Hindi), transcribed once by Gnani Prisma (`eval/stt_results.md`), each transcript replayed 3× on the real phone. Success = harness predicate on the live screen after the run. Dry-run tasks stop before the commit tap (alarm Done, timer Start, Call, Send); sending/calling is disabled entirely (user rule). STT errors are included: a misheard clip counts as a fail.

**Overall: 9/9 (100%)** · median wall 7.8 s

| split | pass | median s |
|---|---|---|
| Telugu | - | - |
| Hindi | - | - |
| routed to a deterministic handler / safety block | - | - |
| routed to the LLM agent loop | 9/9 (100%) | 7.8 |

| task | te | hi | median s | routes seen | failure reasons |
|---|---|---|---|---|---|
| calc_12x8 | - | - | 5.0 | agent |  |
| world_clock | - | - | 7.8 | agent |  |
| timer_tab | - | - | 12.0 | agent |  |

Agent-loop runs: 9 · steps jev 21 / groq 3 · mean steps per run 2.7 · planner seconds per step 2.05 · median planner s per run 3.4
