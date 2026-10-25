# campus-perks

A Cubbie Skill that finds free student software and learning tools, starting with what the student's university
already pays for and the tools their major needs. It checks the terms on official pages, explains the catch, shows
what each offer is worth, and tracks claims, renewals and new offers. Built for Track 1 of the Cubbie Hackathon.

## Install

Text this repository's link to Cubbie and reply "yes" when it asks.

## Try it

- "What free software can I get as an ASU student?"
- "I'm an electrical engineering major, what software do I need?"
- "I claimed the GitHub pack."
- "How much have I saved so far?"
- "Check every week for new student offers."

## Test the helper script locally

    T=$(mktemp -d)
    HOME=$T python3 scripts/state.py --sample diff --record     # 3 new, value.unclaimed_usd 340
    HOME=$T python3 scripts/state.py --sample mark --id jetbrains-students --status claimed
    HOME=$T python3 scripts/state.py --sample list              # claimed_value_usd 100

The sample prices are made up for testing.
