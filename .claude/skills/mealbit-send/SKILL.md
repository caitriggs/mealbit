---
name: mealbit-send
description: Render this week's Mealbit newsletter and send it — a [TEST] to the person alone first, the household only when they've seen one and asked. Covers running the send through GitHub Actions (the normal path, since the container usually can't reach Gmail's SMTP), reading the run, and what each failure means. Use for "send me a test", "send this week's", "did Saturday's go out", or any send-related question.
---

# Rendering and sending

## The two rules

1. **Test to the person first, every time the design changed.** `self` / `--test` goes to
   `MEALBIT_SEND_TEST_TO` alone. Nothing reaches the household address until they've
   looked at a test and said so.
2. **Only a real send writes history.** `data/history.json` is how next week avoids
   repeating this one. A test never touches it, so testing is free.

## Render locally first (no email involved)

```bash
python -m mealbit.meal_plan                 # out/meal_plan.html, out/cards.pdf, out/shopping-list.html
python tools/screenshot.py                  # out/mealbit-412-light.png and -dark.png
```

Open the screenshot and look before sending anything. Things that have been wrong before
and are worth a glance: a per-plate line naming the wrong person, a store code that isn't
theirs, "two sheets" when there are five, a coffee drink paired with the wrong syrup.

Preview any week with `--today 2026-01-10`. Nothing is written.

## Sending: GitHub Actions is the normal path

The container Claude Code runs in usually **cannot open an SMTP connection**, so a local
`--send` fails with a network error that looks like a bug and isn't. The weekly workflow
runs on GitHub's machines, which can. Use it:

**If you have GitHub tools available** (an `actions_run_trigger` or similar tool):
trigger the workflow `meal-plan.yml` on the fork's **default branch** with inputs
`recipient: self`. Then poll the run and read the "Send the newsletter" step's log; it
ends with `sent to <address>` on success.

**If you don't**, tell them in their browser:

1. "Open your fork on GitHub → the **Actions** tab → **Mealbit** in the left list."
2. "Click **Run workflow** (right side). Leave `recipient` as **self**. Click the green
   **Run workflow** button."
3. "It takes about two minutes. When the row goes green, check your inbox — and spam."

For the real send: same thing with `recipient: household`, only when asked in so many
words. Say back what you're about to do and who will receive it before you do it.

Other inputs: `today` previews a different week's plan; `box` and `box_leftovers` handle a
week where a meal kit already covers the first dinners.

## The scheduled send

The workflow fires on its own each week at `send.day` / `send.hour` in
`config/household.yml`, evaluated in `household.timezone` — **if a schedule has been
written.** The template ships with none. `python tools/schedule.py` shows what the config
implies and what the workflow holds; `--write` writes the cron lines (one per UTC offset
the zone uses) and they get committed. Before sending, the job re-checks the local day
and hour, tolerates a firing up to eight hours late — GitHub's cron often is — and stands
down if `data/history.json` already holds the week. "It never came on Saturday" is
therefore one of: no schedule written, not on the default branch, Actions not enabled on
a fork, or a secret missing. `tools/schedule.py` and `tools/setup_status.py` tell you
which.

The workflow **only runs from the default branch.** If the Actions tab shows nothing on
Saturday, that's why.

## Reading a failed run

| Step that failed | What it means | What to do |
|---|---|---|
| Check the household is set up | placeholder addresses and no `MEALBIT_SEND_*` secrets | `.claude/skills/mealbit-secrets` |
| Run the test suite | a config or recipe file breaks a rule | the message names the file and the rule; fix it, don't skip the test |
| Send the newsletter — `535 Username and Password not accepted` | wrong/revoked app password, or it belongs to a different account than `MEALBIT_SEND_FROM` | new app password |
| Send the newsletter — `SMTPRecipientsRefused` | an address secret has a typo | re-read the four secrets' names and values with them |
| Install Chromium | Playwright couldn't install | not fatal — the cards go as HTML instead of PDF; it says so in the log |

## Sending through Claude's Gmail connector instead

Possible for a quick text check, and not recommended for the send people read: the
connector strips inline `<img>` tags, so the meal photos don't render, and attachments
arrive differently. The SMTP path — the workflow — is the one the design was tested on.
