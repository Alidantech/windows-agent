# Task routing and completion design

Windows Agent uses two execution routes inside the same persistent terminal.

## Terminal conversation

Greetings, acknowledgements, and general questions are answered directly in the terminal. This route:

- performs one model request;
- does not capture a monitor;
- does not create a control lease;
- does not execute tools;
- does not run the visual completion verifier;
- returns to `you ❯` immediately.

Examples:

```text
hello ai
How does Chrome work?
What are your current settings?
```

A question that explicitly asks Windows Agent to inspect the computer remains a desktop task:

```text
What is visible on monitor 3?
Can you open Chrome?
```

## Actionable desktop tasks

Explicit requests to open, navigate, click, type, fill, submit, inspect, test, upload, download, or otherwise operate an application use the visual desktop loop.

The router is deterministic for obvious cases. This avoids an additional coordinator-model request on every terminal message and prevents conversation from being forced through screenshot verification.

## Persistent browser continuation

The isolated browser survives between terminal tasks. Follow-ups such as these bind the existing browser before the first screenshot:

```text
create an account and proceed
continue
fill the form
log in
enter the verification code
```

This prevents a follow-up task from observing the entire monitor and attempting a physical coordinate click before rediscovering the browser.

## Personal data, credentials, and consent

The planner is not allowed to invent or guess:

- names;
- email addresses;
- phone numbers;
- addresses;
- usernames;
- company names;
- dates of birth;
- passwords, PINs, or security answers;
- OTP, MFA, or verification codes.

When a required value was not explicitly supplied by the user, the loop pauses and changes the persistent prompt to `answer ❯` or `secret ❯`. Sensitive answers are masked and are not written to prompt history.

Terms, privacy policies, marketing consent, subscriptions, and other legal consent require an explicit user response such as `I agree`. CAPTCHA and human-verification controls require user takeover; Windows Agent does not attempt to bypass them.

## Completion rules

Conversation finishes from the direct terminal response and never enters visual verification.

Desktop completion uses a fresh observation. For browser tasks, Windows Agent waits briefly after navigation or form submission, captures the current page again, and passes that fresh state plus the last tool result to the verifier.

Examples:

- Opening a requested URL is complete when that URL or its valid redirect is visibly open.
- Reaching an email-verification page proves account-form submission, but the account is not fully verified; the agent asks for the code.
- A deterministic smoke-test report completes directly from tool evidence.
- Two rejected completion claims stop the run with an honest incomplete result instead of looping through the full step budget.

## Design sources

The implementation follows several established agent-design principles:

- route requests to the specialized execution path that actually needs them;
- avoid unnecessary coordinator/model calls when deterministic routing is sufficient;
- preserve an editable prompt while background worker output is printed;
- ask for user confirmation or takeover at sensitive and consequential steps;
- keep the user in control of credentials, CAPTCHA, consent, and external side effects.

Official references:

- https://docs.cloud.google.com/architecture/choose-design-pattern-agentic-ai-system
- https://docs.cloud.google.com/architecture/agentic-ai-multimodal-graph-rag-resource-orchestration
- https://python-prompt-toolkit.readthedocs.io/en/stable/pages/asking_for_input.html
- https://python-prompt-toolkit.readthedocs.io/en/stable/pages/reference.html
- https://openai.com/index/computer-using-agent/
- https://openai.com/index/introducing-operator/
