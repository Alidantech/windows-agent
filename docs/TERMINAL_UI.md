# Persistent terminal UI

Windows Agent uses one long-lived `prompt_toolkit` input session and a Rich output feed.

## Relationship glyphs

- `⏺` starts an agent statement, model change, tool action, completion or failure.
- `⎿` introduces the result, reason, evidence or other detail nested beneath that action.
- Indentation carries nesting; glyphs are not repeated for every wrapped line.
- Green means success, red means failure, yellow means waiting/recovery and dim text is secondary metadata.

## Input

The persistent prompt is:

```text
you ❯
```

When the agent asks for guidance it changes to:

```text
answer ❯
```

The bottom toolbar shows idle/working state, selected route, target and queue length. Prompt history, auto-suggest and fuzzy slash-command completion are enabled.

## Progress

A quiet animated status is shown while a model is planning or completion is being verified. Completed actions remain in the continuous feed above the editable prompt.

## Queue and cancellation

The input loop and execution worker are separate. Users can enqueue more tasks while a task is running. Ctrl+C cancels the active task rather than terminating the whole console. `/exit` closes the console and cleans up Windows Agent-owned processes.
