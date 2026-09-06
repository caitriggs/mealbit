---
name: mealbit-secrets
description: Walk a non-technical person, step by step and in their browser, through creating a Gmail app password and adding the four repository secrets (GMAIL_APP_PASSWORD, MEALBIT_SEND_FROM, MEALBIT_SEND_TO, MEALBIT_SEND_TEST_TO) that let their fork send email without any address ever being committed. Use after onboarding, or whenever a send fails with "addresses are placeholders" or a Gmail login error.
---

# Secrets: the one part you cannot do for them

You can write every config file, but you **cannot** create a Gmail app password or add a
GitHub secret — both happen in their browser, signed in as them. Your job is to make each
step one sentence long, wait for them to say it's done, and never ask them to paste a
secret into the chat.

**Never ask for the password, and never ask for it to be typed here.** If they paste it
anyway, tell them to revoke it at <https://myaccount.google.com/apppasswords> and make a
new one, and do not write it anywhere.

## Why four secrets

Their fork is a copy of a public repository, and the config file carries placeholder
addresses so nothing personal is committed. The real addresses and the password live in
**repository secrets** — encrypted values GitHub hands to the weekly job and shows to
nobody, including them, after saving.

| Secret | What goes in it |
|---|---|
| `GMAIL_APP_PASSWORD` | the 16-character app password from step 1 |
| `MEALBIT_SEND_FROM` | the Gmail address that sends (the account the password belongs to) |
| `MEALBIT_SEND_TO` | where the real weekly email goes — often a shared household address |
| `MEALBIT_SEND_TEST_TO` | where test sends go — usually their own address. **Must differ from `MEALBIT_SEND_TO`** |

If `TO` and `TEST_TO` are the same, a test would reach the whole household. The code
refuses that combination; tell them why rather than letting it fail later.

## Step 1 — Gmail app password (about 3 minutes)

Say each of these, one at a time, and wait:

1. "Sign in to the Gmail account you want the email to come *from*."
2. "Open <https://myaccount.google.com/security>. Under *How you sign in to Google*, is
   **2-Step Verification** on?" — If not: "Turn it on; Google walks you through it. App
   passwords only exist once that's on."
3. "Now open <https://myaccount.google.com/apppasswords>. In the box, type **Mealbit**
   and click *Create*."
4. "Google shows a 16-character password in four groups. Leave that window open — you'll
   copy it into GitHub in a moment. Don't send it to me."

If they can't find App passwords: it's hidden when 2-Step Verification is off, and for some
Google Workspace accounts an administrator has disabled it. Say so plainly.

## Step 2 — repository secrets (about 5 minutes)

1. "Open your fork on GitHub. Click **Settings** (the tab on the far right of the
   repository, not your profile settings)."
2. "In the left sidebar, open **Secrets and variables**, then **Actions**."
3. "Click **New repository secret**. Name: `GMAIL_APP_PASSWORD`. Secret: paste the
   16 characters from Google — spaces or no spaces, either works. **Add secret**."
4. Repeat for the three addresses, one at a time. Give them the exact name to type each
   time; names are case-sensitive and a typo here fails silently later:
   - `MEALBIT_SEND_FROM`
   - `MEALBIT_SEND_TO`
   - `MEALBIT_SEND_TEST_TO`
5. "You should see four names listed. GitHub won't show the values again — that's
   expected."

## Step 3 — check it worked, without sending to anyone else

The check *is* a test send to them alone. Hand off to
**`.claude/skills/mealbit-send/SKILL.md`** and run the `self` test. What the failures mean:

- **"the send addresses are placeholders and the three MEALBIT_SEND_* secrets are not
  set"** — a secret name is misspelled or missing. Have them re-open the Secrets page and
  read the four names back to you.
- **`535 Username and Password not accepted`** — the app password is wrong, was revoked,
  or belongs to a different account than `MEALBIT_SEND_FROM`. Make a new one.
- **Nothing arrives but the job is green** — check spam, then confirm
  `MEALBIT_SEND_TEST_TO` is the address they're looking in.

## Also: the Actions workflow only runs from the default branch

If the weekly email never comes and the Actions tab is empty, one of three things: the
workflow file isn't on the default branch (check Settings → General → Default branch),
no schedule has been written (`python tools/schedule.py` says so; `--write` fixes it), or
— on a fork — GitHub has scheduled workflows switched off until someone opens the
**Actions** tab and presses **I understand my workflows, go ahead and enable them**. A
repository made with "Use this template" has Actions on from the start.

## Optional secret: Pexels

`PEXELS_API_KEY` is only needed to fetch stock photos for **new** recipes they add. The
library ships with photos. Don't raise it during onboarding.
