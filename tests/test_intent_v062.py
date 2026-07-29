from agent_os.intent import IntentRouter


def test_greeting_routes_to_conversation():
    route = IntentRouter().route("hello ai")
    assert route.kind == "conversation"
    assert route.continue_browser is False


def test_general_question_routes_to_conversation():
    route = IntentRouter().route("How well are you performing?")
    assert route.kind == "conversation"


def test_screen_question_routes_to_desktop():
    route = IntentRouter().route("What is visible on monitor 3?")
    assert route.kind == "desktop"


def test_url_task_routes_to_desktop():
    route = IntentRouter().route("open chrome and visit app.defytickets.co")
    assert route.kind == "desktop"


def test_browser_continuation_binds_existing_session():
    route = IntentRouter().route("create an account and proceed", browser_active=True)
    assert route.kind == "desktop"
    assert route.continue_browser is True


def test_question_about_browser_routes_to_conversation():
    route = IntentRouter().route("How does Chrome work?")
    assert route.kind == "conversation"


def test_question_requesting_browser_action_routes_to_desktop():
    route = IntentRouter().route("Can you open Chrome?")
    assert route.kind == "desktop"
