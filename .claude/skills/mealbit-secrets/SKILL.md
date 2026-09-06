---
name: mealbit-secrets
description: Walk a non-technical person, step by step and in their browser, through creating a Gmail app password and adding the five secrets (GMAIL_APP_PASSWORD, MEALBIT_SEND_FROM, MEALBIT_SEND_TO, MEALBIT_SEND_TEST_TO, PEXELS_API_KEY) that let their copy send email and fetch recipe photos without any address or key ever being committed. Use after onboarding, or whenever a send fails with "addresses are placeholders" or a Gmail login error.
---

# Secrets: the one part you cannot do for them

You can write every config file, but you **cannot** create a Gmail app password or add a
GitHub secret — both happen in their browser, signed in as them. Your job is to make each
step one sentence long, wait for them to say it's done, and never ask them to paste a
secret into the chat.

**Never ask for the password, and never ask for it to be typed here.** If they paste it
anyway, tell them to revoke it at <https://myaccount.google.com/apppasswords> and make a
new one, and do not write it anywhere.

## Why five secrets

Their copy came from a public template, and the config file carries placeholder addresses
so nothing personal is committed. The real addresses, the password and the photo key live
in **secrets** — encrypted values shown to nobody, including them, after saving.

| Secret | What goes in it | Where it is used |
|---|---|---|
| `GMAIL_APP_PASSWORD` | the 16-character app password from step 1 | the weekly send, on GitHub |
| `MEALBIT_SEND_FROM` | the Gmail address that sends (the account the password belongs to) | the weekly send |
| `MEALBIT_SEND_TO` | where the real weekly email goes — often a shared household address | the weekly send |
| `MEALBIT_SEND_TEST_TO` | where test sends go — usually their own address. **Must differ from `MEALBIT_SEND_TO`** | the weekly send |
| `PEXELS_API_KEY` | a free key from Pexels, for the photo on every new recipe's card | **this Claude Code session**, when you write a recipe |

The first four are GitHub repository secrets; the weekly job reads them. The fifth is
different: the photo tool runs *here*, in the Claude Code session, which never sees
GitHub's secrets. So the Pexels key goes into the **Claude Code environment** (and into
GitHub too, so it is in one place they can find later). Without it, every recipe you write
for them prints a card with no photo.

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

## Step 3 — the Pexels key, for recipe photos (about 3 minutes)

1. "Open <https://www.pexels.com/api/> and press **Get Started**. Sign up or sign in;
   it's free."
2. "Once you're in, the page shows **Your API Key** — a long string. Leave it open."
3. "Back on GitHub, same Secrets page: **New repository secret**, name `PEXELS_API_KEY`,
   paste the key, **Add secret**." (Five names listed now.)
4. "One more place, because I fetch the photos from here, not from GitHub: open
   <https://claude.ai/code>, open **Settings**, then **Environments**, pick the
   environment this repository uses, and under **Environment variables** add
   `PEXELS_API_KEY` with the same key. Save."
5. "Tell me when that's done and I'll check I can see it." Then run
   `python tools/setup_status.py`; its Pexels line says whether the key reached this
   session. If not, the session needs restarting after the environment change — say so in
   one sentence.

If they'd rather not sign up for Pexels: fine, the emails still send. Say that any new
dish gets a card with a labelled blank where the photo goes, and move on.

## Step 4 — check it worked, without sending to anyone else

The check *is* a test send to them alone. Hand off to
**`.claude/skills/mealbit-send/SKILL.md`** and run the `self` test. What the failures mean:

- **"the send addresses are placeholders and the three MEALBIT_SEND_* secrets are not
  set"** — a secret name is misspelled or missing. Have them re-open the Secrets page and
  read the names back to you.
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

## If a recipe was written before the key existed

`photo_pending: true` marks it. Once `setup_status.py` shows the key in this session, run
`python tools/stock_photos.py --sheet <slug>` for each pending recipe, look, pin — see
`.claude/skills/mealbit-recipes`, "Photos and the source link".
