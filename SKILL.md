---
name: campus-perks
description: Finds free software and learning tools a college student can actually claim, starting with what their own university already pays for and the tools their major needs. Checks terms on official pages, explains the catch, shows what each offer is worth, and tracks claims and renewal dates. Use when a student asks about student discounts, free software, student perks, software for their classes or major, how much they have saved, or wants alerts for new student offers.
---

# campus-perks

Answers one question for a student: "What can I actually get for free, what's the catch, and when do I need to act?"
It checks official provider and university pages, explains the conditions, shows what each offer would normally
cost, remembers what the student claimed or dismissed, and offers weekly checks and renewal reminders.

This is not a general shopping or coupon Skill. It covers software, AI tools, coding tools, engineering tools,
design tools, productivity tools, learning subscriptions and services the student's university provides.

## When to use

- "What free software can I get as an ASU student?"
- "I'm an electrical engineering major, what software do I need for my classes?"
- "Any student deals on coding or AI tools?"
- "I just started college, what perks am I missing?"
- "Is the JetBrains student license still free?"
- "How much have I saved so far?"
- "Check every week for new student offers."
- "I claimed the GitHub pack." / "Not interested in Figma."

Do not use it for food, clothing or travel coupons, campus events, or scholarships.

## Files

- `sources.json`: the official pages to check, tagged by `categories` and `scope` (any student, or one university).
- `scripts/state.py`: saves the student's profile and offer decisions, filters out offers already shown, claimed
  or dismissed, and adds up offer values. It only uses the Python standard library, so there is no setup step.
- `assets/sample_offers.json`: example input for testing the script.

## Steps

### 1. Profile (first time only)

Run from this Skill's folder:

```bash
python3 scripts/state.py profile --show
```

If it prints `"profile": null`, ask only two questions, one at a time:

1. "Which university do you go to?"
2. "What's your major? (or 'undecided')"

Then pick `interests` from the major:

| Major | interests |
| --- | --- |
| Any engineering (electrical, computer, mechanical, civil, biomedical...) | engineering, coding, productivity |
| Computer science, software, data science, informatics | coding, ai, productivity |
| Design, art, architecture, film, media | design, productivity |
| Anything else, or undecided | productivity, learning, ai |

Tell the student the defaults in one line, so they can change them without more questions:
"Got it. I'll look for free offers in the US for <interests>. Reply 'include paid' or name other topics anytime."

Save the profile:

```bash
python3 scripts/state.py profile --set '{"university": "<university>", "major": "<major>", "country": "United States", "interests": ["<interest>", "..."], "free_only": true}'
```

If the student later changes something ("include paid", "I'm in Canada", "add design"), save only that field with
`profile --set`. If they mention offers they already have, run the `mark` command from step 5 with
`--status claimed` for each.

### 2. Find and verify offers

1. Read `sources.json`. Keep sources that share at least one of `categories` with the student's interests and whose
   `scope` is `any` or the student's university. Check the student's own university sources first: those are
   benefits they have already paid for through tuition. Skip sources marked `"paid": true` when the student chose
   free only. If a source has a `requires` note, tell the student that condition with the offer.
2. Open each kept source's `url` with Cubbie's web reading ability. Read only that page and pages it links to on the
   same official site.
3. A general web search may find more candidates, but only recommend an offer after reading its terms on the
   provider's or the university's own website.
4. For each offer, write down these fields, copied from what the page says:
   - `id`: the source's `id` from `sources.json`, or a short lowercase name for a new offer
   - `provider`, `benefit`, `official_url`
   - `eligibility`: who qualifies (enrolled student, school email, major, age, country)
   - `deadline`: last day to claim, or `unknown`
   - `payment_required`: `yes`, `no` or `unknown` (does signing up need a card?)
   - `renewal_terms`: what happens after the free period (renewal price, re-verification), or `unknown`
   - `value_usd`: what one year of the same plan costs a non-student, as a number, read from the provider's own
     pricing page. Use `"unknown"` for bundles with no single price or when no official price is shown.
   - `last_checked`: today's date as YYYY-MM-DD
   Use `unknown` for anything the page does not state. Never fill a field from memory.
5. If a page cannot be opened, note that source as unverified. That means "couldn't check", not "no offer".
6. Drop an offer if the page says it has ended, if it excludes the student's country, or if it needs payment and
   the student chose free only.

### 3. Filter out what the student has already seen

Save the offers from step 2 as JSON to a temporary file, for example `/tmp/campus_perks_offers.json`, as
`{"offers": [ ... ]}`. Then run:

```bash
python3 scripts/state.py diff --offers /tmp/campus_perks_offers.json --record
```

It prints JSON with `new`, `changed` (terms differ from what the student saw before), `unchanged`, `suppressed`
(claimed or dismissed), and `value.unclaimed_usd` (the yearly value of everything not yet claimed or dismissed).
Recommend only `new` and `changed` offers. `--record` saves them as shown so the next check doesn't repeat them.

### 4. Reply

Send at most three offers. Put offers from the student's own university first, then the best match for their
major. If `value.unclaimed_usd` is above 0, open with one line:
"You're not using about $<unclaimed_usd> a year in student perks. Here's where to start:"
Use "about" because list prices change, and leave the line out when the value is 0.

For each offer:

```text
GitHub Student Developer Pack
Free bundle of developer tools while you're a student
Worth: no single price, it's a bundle
Catch: needs proof of enrollment; tools renew at normal price after you graduate
Claim by: no deadline listed
https://education.github.com/pack
```

Write `Worth: about $<value_usd>/yr` when `value_usd` is a number. For offers from the student's university, start
the second line with "<university> already pays for this:".

Then one line listing any sources you couldn't verify, and one question:
"Want me to check for new offers every week? Sunday 10 am?"

If `eligibility` is unclear, say "Check eligibility: <what is unclear>". Never tell the student they qualify when
the page doesn't say so.

### 5. Track decisions

When the student says they claimed, saved or don't want an offer:

```bash
python3 scripts/state.py mark --id <offer id> --status <claimed|saved|dismissed>
```

When they claim a free trial or a time-limited plan, ask for the activation date (default: today), then run the same
command with `--activated YYYY-MM-DD`. If the offer has a known renewal or end date, offer a reminder 7 days before
it in the student's time zone, and create it with Cubbie's reminders ability only after the student says yes.
The reminder names this Skill, the provider, what renews or ends, the date, and the official link.

### 6. "How much have I saved?"

```bash
python3 scripts/state.py list
```

Reply with `claimed_value_usd` in one line, for example "You've claimed about $<claimed_value_usd> a year in
student perks." If `claimed_value_unknown_count` is above 0, add "plus <n> with no listed price." If nothing is
claimed yet, offer to find something.

### 7. Weekly check (only with the student's yes)

Create the scheduled check-in at the day and time the student picks. Word it so it makes sense on its own later:

"campus-perks weekly check: open the campus-perks Skill, check its sources for new or changed
student software offers, run its diff step with --record, and text the student only if something is new or changed."

If nothing is new, send nothing. If the student says stop, delete the check-in and confirm in one line. Saved
profile and decisions stay unless the student asks to delete them, in which case run:

```bash
python3 scripts/state.py reset --yes
```

## Replies

- Short plain text, one offer per block, no Markdown symbols, no tables.
- Every link on its own line, and only official links.
- Always include the catch: eligibility, payment, renewal. That is the point of this Skill.
- Dollar values are always "about" and only from official pricing pages. Never estimate one.
- More than three good matches: send the top three and offer the rest.

## When something fails

| Situation | What to text |
| --- | --- |
| No offers matched | "Nothing new that fits right now. Want me to include paid discounts?" (skip the question if they already do) |
| Some pages couldn't be opened | List them in one line as "Couldn't verify: ..." and still send what was verified |
| Every page failed | "I couldn't reach the offer pages right now. Want me to try again in an hour?" Never say there are no offers. |
| Script exit code 2 | The input was malformed; fix the JSON and run once more. Do not retry more than once. |
| Script exit code 3 | Saved data is unreadable. Tell the student and offer to reset it with `reset --yes`. |
