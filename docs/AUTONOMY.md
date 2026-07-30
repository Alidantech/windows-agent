# Bounded autonomy

Windows Agent separates reversible inference from protected decisions.

## Autonomous choices

When the task or later guidance contains `demo`, `sample`, `test`, `mock`, `fill yourself`, `use defaults`, `decide for me`, or equivalent delegation, the active task receives an autonomy grant.

The grant permits the agent to choose reversible, non-personal values such as:

- demo titles and short names;
- unique slugs;
- future dates and times;
- neutral categories from visible options;
- an existing valid timezone or a safe fallback;
- General Admission seating;
- non-broadcast mode;
- ordinary capacities;
- optional-field omission.

The generated event plan is stable for the task. If the model asks for the same ordinary fields again, the question broker returns the existing plan internally instead of interrupting the user.

## Protected boundaries

The grant never covers:

- personal identity or contact details;
- passwords, PINs, OTPs, API keys, or security answers;
- CAPTCHA or human verification;
- legal terms, privacy consent, marketing subscriptions, or newsletters;
- payment or financial details;
- publishing, sending, purchasing, deleting, refunding, or other consequential actions.

These boundaries continue to require explicit user input or approval.

## Routing

An active persistent browser is treated as context. Follow-ups such as `create an event`, `use the browser`, `do it`, and typo-level variants such as `creaye an event` continue in the bound browser instead of being answered as terminal conversation.

## Demo event defaults

For an authorized demo event, Windows Agent supplies:

- title: `Windows Agent Demo Event`;
- short name: `Agent Demo`;
- a timestamped unique URL slug;
- a start time at 10:00 on the following day;
- an end time two hours later;
- capacity 100;
- category preference: Technology, Conference, Workshop, Other;
- timezone preference: existing valid value, Africa/Nairobi, UTC;
- seating preference: General Admission;
- online/broadcast: No unless explicitly requested.

The planner still verifies each field and selection against the live page.
