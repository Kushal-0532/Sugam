# Sugam: a phone you can just talk to

## The problem
Phones basically assume you can read English menus and tap tiny buttons. A lot of people can't do either, my grandmother included, so even something as small as setting an alarm means asking someone else to do it.

## What Sugam does
You just say what you want, in Telugu, Hindi, English or whatever mix comes out (which is how most of us actually talk), and a real Android phone does it. It sets the alarm, searches YouTube, finds a pharmacy on Maps, gets a call ready, and then tells you out loud what it did, in the same language you used.

## Where Gnani AI comes in
- **Prisma v3.0** (speech to text) does the listening. It handles code-mixing properly, so the English words in a Telugu or Hindi sentence stay English instead of getting mangled.
- **Timbre v3.0** (text to speech) does the talking. Every reply and every "are you sure?" is spoken back in your language.

## How it works
- **Guardrails go first.** These are plain rules, not a prompt, so payment requests and private apps like WhatsApp get blocked before any AI even sees them.
- **A router picks the path.** Jev decides, and a Groq LLM steps in when Jev isn't sure. Tasks with predefined steps (alarm, timer, call, YouTube, Maps) run as a workflow: fixed steps I wrote and tested, where the LLM only fills in details like the time.
- **Tasks with unknown steps go to an agent.** It reads the phone's screen, the LLM picks one action, the guardrails check it, and the bot taps. Then it looks at the screen again, until it's done.
- **Anything risky waits for a spoken yes**, like placing a call. Calling and messaging are switched off in this build anyway.

## How well it works
52 of the 72 Telugu and Hindi commands I recorded passed on a real phone (72%), with a median of 8 s per task. Most failures were the speech getting misheard, and when a misheard command ends up with the agent it usually can't recover, so that's kinda where the work is left.

## What's next
Right now the phone has to be plugged into a laptop. The next version is a standalone Android app, so no laptop and no cable.

Built solo. Code (MIT): https://github.com/Kushal-0532/Sugam
