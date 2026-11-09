# Agent eval — agent_jev_calc

2026-11-06 19:25 · CPH2491 (Android 16) · planner jev · LLM openai/gpt-oss-120b (reasoning low) · commit uncommitted · STT transcripts: default (te,hi,en auto-detect)

**PARTIAL: stopped early: LLM rate limit at calc_12x8_typed#1. Only 1 runs below.**

Input: the user's 24 recorded clips (12 commands × Telugu/Hindi), transcribed once by Gnani Prisma (`eval/stt_results.md`), each transcript replayed 3× on the real phone. Success = harness predicate on the live screen after the run. Dry-run tasks stop before the commit tap (alarm Done, timer Start, Call, Send); sending/calling is disabled entirely (user rule). STT errors are included: a misheard clip counts as a fail.

**Overall: 1/1 (100%)** · median wall 37.7 s

| split | pass | median s |
|---|---|---|
| Telugu | - | - |
| Hindi | - | - |
| routed to a deterministic handler / safety block | - | - |
| routed to the LLM agent loop | 1/1 (100%) | 37.7 |

| task | te | hi | median s | routes seen | failure reasons |
|---|---|---|---|---|---|
| calc_12x8 | - | - | 37.7 | agent |  |

Agent-loop runs: 1 · steps jev 5 / groq 2 · mean steps per run 7.0 · planner seconds per step 3.38 · median planner s per run 23.7
