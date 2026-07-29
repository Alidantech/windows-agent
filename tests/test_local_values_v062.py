import threading
import time

from agent_os.cancellation import CancellationToken
from agent_os.local_values import LOCAL_VALUE_TOKEN, local_value_vault
from agent_os.session import QuestionBroker


def test_sensitive_answer_returns_token_and_stays_local():
    local_value_vault.clear()
    broker = QuestionBroker(CancellationToken())
    output: list[str] = []

    thread = threading.Thread(
        target=lambda: output.append(
            broker.ask("Enter the password to use", sensitive=True)
        )
    )
    thread.start()
    for _ in range(100):
        if broker.pending_question:
            break
        time.sleep(0.01)

    assert broker.pending_sensitive is True
    assert broker.answer("not-sent-to-model") is True
    thread.join(timeout=2)

    assert output == [LOCAL_VALUE_TOKEN]
    assert local_value_vault.get() == "not-sent-to-model"
    broker.cancel()
    assert local_value_vault.get() is None
