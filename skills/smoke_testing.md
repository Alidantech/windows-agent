---
name: smoke-testing
description: Deterministic same-origin website link testing.
triggers: [smoke test, test every link, test all links, navigation links, visit each link, website test]
---
After opening the starting page in the isolated browser, use `smoke_test_site` with an appropriate `max_links`. It inventories unique same-origin anchors, opens each URL in an isolated page, records HTTP status, final URL, title, page errors, failed requests, duration, and a screenshot, and writes a JSON report.

Do not manually click links one at a time unless the task explicitly requires interaction behavior. Completion requires report counts and the report path. Report failures honestly.
