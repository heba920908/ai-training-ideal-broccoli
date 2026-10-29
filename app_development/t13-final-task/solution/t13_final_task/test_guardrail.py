import pytest
from t13_final_task.task.agent.guardrail import UMSDataGuardrail

pytest.importorskip("en_core_web_sm", reason="spaCy model en_core_web_sm is not installed")

# Synthetic record in the UMS MCP output shape; numbers are fake and Luhn-invalid.
UMS_RECORD = """```
  id: 1001
  name: Fixture
  surname: Person
  email: fixture.person@example.com
  salary: 85000.5
  credit_card: {'num': '1234-5678-9012-3456', 'cvv': '259', 'exp_date': '08/2029'}
```"""


@pytest.fixture(scope="module")
def guardrail():
    return UMSDataGuardrail()


def test_ums_yaml_record_redacted(guardrail):
    result = guardrail.redact(UMS_RECORD)
    for secret in ("85000.5", "1234-5678-9012-3456", "'259'", "08/2029"):
        assert secret not in result
    assert "salary: ***" in result
    assert "'num': '***'" in result and "'cvv': '***'" in result
    assert "'exp_date': '***'" in result
    assert "fixture.person@example.com" in result and "name: Fixture" in result


def test_json_record_redacted(guardrail):
    text = '{"salary": 120000, "credit_card": {"num": "1111 2222 3333 4444", "cvv": "1234", "exp_date": "01/2030"}}'
    result = guardrail.redact(text)
    for secret in ("120000", "1111 2222 3333 4444", "1234", "01/2030"):
        assert secret not in result


def test_python_dict_salary_and_standalone_card(guardrail):
    result = guardrail.redact("{'salary': 99000} card 9999-8888-7777-6666 on file")
    assert "99000" not in result and "9999-8888-7777-6666" not in result


def test_plain_text_salary(guardrail):
    assert "85,000" not in guardrail.redact("Annual salary: $85,000")


@pytest.mark.parametrize(
    "text", ["salary: None", "No users found", "OpenAI announced a new model today."]
)
def test_non_pii_unchanged(guardrail, text):
    assert guardrail.redact(text) == text
