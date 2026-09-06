# Setting up Mealbit for your household

**The easy way:** fork this repository, open your fork in Claude Code, and say hello.
Claude runs the setup survey, writes the config from your answers, and walks you through
the secrets in your browser. Everything below is what it does — read on if you'd rather
do it yourself, or want to know what's happening.

About twenty minutes, honestly. Most of it is waiting on Google to give you an app
password.

You'll end up with a weekly email — four dinners, a lunch plan, a shopping list grouped by
the shops *you* visit, printable recipe cards and one coffee drink worth making — that
arrives on the day and hour you pick, planned from a library you can read and edit.

## 1. Make your copy

Press **Use this template** on the repository page and make the new repository
**private**: your household config (first names, what you won't eat) lives in it, by
design, so you can see and version it. A fork works too, but GitHub won't let a fork of a
public repository be made private. Either kind of copy can take fixes from upstream —
`config/upstream.yml` names it.

Clone it and install:

```bash
git clone <your fork>
cd mealbit
pip install -r requirements.txt
python tests/test_mealbit.py         # 80 tests; they pass on the template as shipped
```

## 2. Say who you are — `config/household.yml`

Open it. Everything is commented. The parts that matter:

```yaml
household:
  eaters: [Ada, Sam]                   # two names — see the note below
  timezone: America/Los_Angeles

send:
  from: you@gmail.com                  # the Gmail account that sends
  to: household@example.com            # where the real one goes
  test_to: you@gmail.com               # where --test goes. Must differ from `to`.
  day: Saturday
  hour: 17

diet:
  exclude_ingredients: [shrimp]        # never planned
  per_plate:
    Sam: [cilantro, raw tomatoes]      # Sam skips these; the dish is built without them
```

**Two eaters.** Dinners are cooked to serve four: two at the table, two as the next day's
lunches. That arithmetic is what makes the lunch column free, and it is built on exactly
two people. A household of four is not a config change yet; see
`docs/household-model.md` for what it would take.

**`exclude_ingredients` vs `per_plate`** are different things and the difference is
load-bearing. An exclusion removes every recipe that uses the ingredient. A per-plate item
keeps the recipe, and the ingredient goes on the other plate at the end — every recipe
that buys one has been written to be complete without it, and a test holds that.

The test suite validates the file. It will refuse a `test_to` that equals `to`, because a
test send that reaches the whole household is the one mistake this must never make.

## 3. Say where you shop — `config/stores.yml`

List your shops **in the order you visit them**. The shopping list is grouped in that
order, and each ingredient goes to the first shop whose `takes:` covers what it is.

```yaml
stores:
  - id: market
    short: FM
    name: Ballard Farmers Market
    kind: farmers_market
    when: Sunday 9am–2pm
    where: Ballard Ave NW
    availability: data/markets/pnw-washington-growers.md
    tips: data/markets/west-seattle.md     # copy this and write your own stall notes
    takes: [produce]

  - id: tj
    short: TJ
    name: Trader Joe's
    takes: [protein, dairy, bakery, pantry, specialty, wine]

  - id: safeway
    short: SW
    name: Safeway
    takes: [everything]                    # exactly one shop must be the catch-all
```

Recipes tag every ingredient with what it is — `[produce]`, `[protein]`, `[dairy]`,
`[bakery]`, `[pantry]`, `[specialty]`, `[wine]` — and never name a shop. So adding
Costco, dropping Trader Joe's, or having one supermarket and no market is a change to this
file and nothing else.

**No farmers market?** Delete that entry. The market section of the email disappears and
produce routes to whichever shop takes it.

**A different farmers market?** Keep the `availability:` line if you're anywhere in the
Puget Sound — it's a Washington-growers model and it's the same for every market here.
Copy `data/markets/west-seattle.md` to a file of your own and rewrite the stall tips
after you've actually walked it. Elsewhere in the country, you'll want to write a new
availability model; the file explains its three lists.

## 4. Get a Gmail app password

Sending goes through Gmail's SMTP, from the `send.from` account, using an **app
password** — not your real password.

1. Turn on 2-Step Verification for that Google account, if it isn't already.
2. Go to <https://myaccount.google.com/apppasswords>, name it "Mealbit", copy the
   16-character password.
3. In your fork on GitHub: **Settings → Secrets and variables → Actions → New repository
   secret**, name `GMAIL_APP_PASSWORD`, paste it.

The password never goes in a file. Locally, put it in your shell environment when you
want to send from your machine:

```bash
export GMAIL_APP_PASSWORD='xxxx xxxx xxxx xxxx'
```

**Keeping the repository public?** Then your email addresses shouldn't be in
`household.yml` either. Add three more repository secrets — `MEALBIT_SEND_FROM`,
`MEALBIT_SEND_TO`, `MEALBIT_SEND_TEST_TO` — and leave the placeholders in the file. The
workflow passes them in as environment variables, and an environment value always wins
over the file. For a local send, `export` the same three. A private fork can skip this and
just write the addresses into the file.

## 5. Send yourself one

```bash
python -m mealbit.meal_plan               # renders out/meal_plan.html — open it
python -m mealbit.meal_plan --send --test # [TEST] to send.test_to, and only there
```

Read it on your phone. Check the shop names, the market day, the names on the per-plate
lines. Only when that looks right:

```bash
python -m mealbit.meal_plan --send        # the real thing, to send.to
```

The real send also records the week in `data/history.json`, which is how next week's
plan avoids repeating this one. A `--test` send never writes history.

## 6. Let it run on its own

`.github/workflows/meal-plan.yml` sends every week from GitHub Actions — no computer of
yours needs to be on. Two things to know:

- **The template ships with no schedule**, so the public copy never sends from itself.
  Run `python tools/schedule.py --write` and commit: it reads your day, hour and timezone
  from the config and writes the cron lines (one per UTC offset your zone uses, so
  daylight saving is covered). Before sending, the job checks your local day and hour
  again, accepts a firing up to eight hours late — GitHub's cron often is — and uses
  `data/history.json` to make sure a week is sent once.
- **It only fires from your repository's default branch.** If the workflow file isn't on
  the default branch, nothing happens and nothing tells you. On a fork, GitHub also
  disables scheduled workflows until you press **Enable** on the Actions tab.

You can also run it by hand from the **Actions** tab: choose `self` for a test send,
`household` for the real one.

## 7. Optional: recipe photos

Every card carries a photo. The library ships with them. If you add recipes and want
photos for them, `tools/find_sources.py` looks for a real published version of the dish
(that also gives the card a QR code to the recipe), and `tools/stock_photos.py` falls
back to Pexels stock photography — that one needs a free key from
<https://www.pexels.com/api/> in `PEXELS_API_KEY`. Both tools show you candidates and
make you pick; a photo nobody has looked at cannot reach a card.

## Running it from Claude Code

The repository's `CLAUDE.md` is written for this. Open the folder in Claude Code and ask
it to render this week's plan, add a recipe, change a preference, or send a test — it
knows the rules, the tests, and the things that have gone wrong before.

One caveat if you use Claude's Gmail connector to send instead of the workflow: the
connector strips inline `<img>` tags, so the meal photos don't render, and attachments
arrive differently. The SMTP path (`--send`, locally or via Actions) is the one that
renders the way it was designed. Use the connector for a quick text check, not for the
send people read.

## When something's wrong

- **A recipe file fails a test** → the message names the file and the rule. The tests
  are the guard on hand-edited data; a malformed recipe should fail here, not in the
  inbox.
- **The market list has something the market never sells** → correct
  `data/markets/pnw-washington-growers.md` (or your own model). The email prints every
  reroute it made so you can see what it thinks.
- **A shop is missing from the list** → check `stores.yml` has exactly one `everything`.
- **The send didn't happen on Saturday** → Actions tab. Check the workflow is on the
  default branch and read the "Resolve run parameters" step; it prints the local time
  it saw.
