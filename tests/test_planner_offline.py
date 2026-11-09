from src import safety
def test_denylist():
    assert safety.denied("com.phonepe.app") and safety.denied("com.sbi.lotusintouch")
    assert not safety.denied("com.android.vending") and not safety.denied("com.oneplus.deskclock")


def test_rate_limit_is_its_own_outcome(monkeypatch):
    """Quota exhaustion must not look like an agent failure, and must not fall through to the agent loop."""
    from src import agent, planner
    def limited(*_):
        raise planner.RateLimited("tokens per day")
    monkeypatch.setattr(planner, "understand", limited)
    monkeypatch.setenv("PLANNER", "groq")
    assert agent.run_routed("calculator open karo", say=lambda _: None) == "llm_rate_limited"
