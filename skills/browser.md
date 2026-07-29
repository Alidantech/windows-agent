---
name: browser
description: Independent browser automation with Playwright virtual input.
triggers: [website, site, page, browser, url, link, tab, http, .com, chrome, brave, edge, web, visit]
---
For web tasks, prefer the isolated browser backend. `open_url`, browser element clicks, `fill_element`, page keyboard, and page scrolling operate inside Playwright and do not move the user's Windows cursor or type through the user's keyboard.

Do not activate a system browser repeatedly. Once the lease backend is `browser`, remain inside that session. Use the current browser URL/title, DOM elements, console errors, and request failures as evidence.
