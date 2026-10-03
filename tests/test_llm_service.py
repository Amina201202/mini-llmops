import httpx
import pytest
from openai import RateLimitError

import llm_service


@pytest.fixture(autouse=True)
def clean_state(tmp_path, monkeypatch):
    # her testden evvel cache-i bosaldiram ki testler bir-birine tesir etmesin
    llm_service.CACHE.clear()
    # testler esl costs.csv-ni zibillemesin deye muveqqeti fayla yaziram
    monkeypatch.setattr(llm_service, "COSTS_FILE", tmp_path / "costs.csv")
    # retry zamani heqiqeten gozlemesin, test tez bitsin
    monkeypatch.setattr(llm_service.time, "sleep", lambda s: None)


def make_rate_limit_error():
    # RateLimitError yaratmaq ucun saxta http cavab lazimdir
    request = httpx.Request("POST", "https://fake.api")
    response = httpx.Response(429, request=request)
    return RateLimitError("rate limit", response=response, body=None)


def test_cache_calls_llm_only_once():
    calls = []

    def fake_llm(model, question):
        calls.append(question)
        return "saxta cavab", 10, 20

    first = llm_service.ask("Salam, necəsən?", llm_call=fake_llm)
    second = llm_service.ask("Salam, necəsən?", llm_call=fake_llm)

    assert first == second == "saxta cavab"
    # ikinci defe cache-den gelmelidi, yeni llm cemi 1 defe cagirilib
    assert len(calls) == 1


def test_calculate_cost():
    # 1000 input * 1.50$ + 500 output * 9.00$, hamisi / 1 milyon
    # (1500 + 4500) / 1_000_000 = 0.006
    cost = llm_service.calculate_cost("gemini-3.5-flash", 1000, 500)
    assert cost == pytest.approx(0.006)


def test_fallback_when_primary_fails():
    used_models = []

    def fake_llm(model, question):
        used_models.append(model)
        if model == llm_service.PRIMARY_MODEL:
            raise make_rate_limit_error()
        return "ehtiyat modelden cavab", 10, 20

    answer = llm_service.ask("test sual", llm_call=fake_llm)

    assert answer == "ehtiyat modelden cavab"
    # esas model 3 defe cehd edir, sonra ehtiyat model 1 defe
    assert used_models.count(llm_service.PRIMARY_MODEL) == 3
    assert used_models[-1] == llm_service.FALLBACK_MODEL


def test_error_message_when_all_fail():
    def fake_llm(model, question):
        raise make_rate_limit_error()

    answer = llm_service.ask("test sual", llm_call=fake_llm)

    assert answer == llm_service.ERROR_MESSAGE
    # xeta cavabi cache-e dusmemelidi
    assert "test sual" not in llm_service.CACHE