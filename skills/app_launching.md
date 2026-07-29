---
name: app-launching
description: Launch and focus Windows applications.
triggers: [open app, launch, notepad, calculator, explorer, browser, settings, terminal, paint]
---
Use `launch_app` when the desired program appears in `available_app_aliases`. If the app is already visible, use `activate_window`. After launching, wait only if the next screenshot still shows the prior window or a loading state.
