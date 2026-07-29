from types import SimpleNamespace

from agent_os.interaction_policy import InteractionPolicy, question_is_sensitive
from agent_os.models import AgentDecision, Rectangle, UIElement


def observation(*elements):
    return SimpleNamespace(uia=SimpleNamespace(elements=list(elements)))


def element(element_id: str, name: str, control_type: str = "input") -> UIElement:
    return UIElement(
        element_id=element_id,
        name=name,
        control_type=control_type,
        rect=Rectangle(left=0, top=0, width=10, height=10),
        center_x=10,
        center_y=10,
        source="browser",
    )


def test_blocks_invented_email():
    decision = AgentDecision(
        action="fill_element",
        element_id="B1",
        text="invented@example.com",
        reason="fill email",
    )
    intervention = InteractionPolicy().required_intervention(
        decision,
        observation(element("B1", "Email address")),
        task="create an account",
        guidance=[],
    )
    assert intervention is not None
    assert "email" in intervention.question.lower()
    assert intervention.sensitive is True
    assert intervention.mode == "replace_text"


def test_allows_user_supplied_email():
    decision = AgentDecision(
        action="fill_element",
        element_id="B1",
        text="peter@example.com",
        reason="fill email",
    )
    intervention = InteractionPolicy().required_intervention(
        decision,
        observation(element("B1", "Email address")),
        task="use peter@example.com to create an account",
        guidance=[],
    )
    assert intervention is None


def test_requires_explicit_terms_consent():
    decision = AgentDecision(
        action="click_element",
        element_id="B2",
        reason="accept terms",
    )
    intervention = InteractionPolicy().required_intervention(
        decision,
        observation(element("B2", "I agree to the Terms and Conditions", "checkbox")),
        task="create an account",
        guidance=[],
    )
    assert intervention is not None
    assert "type 'i agree'" in intervention.question.lower()
    assert intervention.mode == "confirm_action"


def test_requires_user_takeover_for_captcha():
    decision = AgentDecision(
        action="click_element",
        element_id="B3",
        reason="complete CAPTCHA",
    )
    intervention = InteractionPolicy().required_intervention(
        decision,
        observation(element("B3", "I'm not a robot reCAPTCHA", "checkbox")),
        task="create an account",
        guidance=[],
    )
    assert intervention is not None
    assert "yourself" in intervention.question.lower()
    assert intervention.mode == "manual"


def test_sensitive_question_detection():
    assert question_is_sensitive("Enter the verification code sent to your email")
    assert question_is_sensitive("What password should I use?")
    assert not question_is_sensitive("What first name should I enter?")
