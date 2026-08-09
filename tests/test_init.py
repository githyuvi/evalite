def test_public_api_imports():
    from evalite import (
        AgentAdapter, AgentResponse, sync_adapter,
        TestCase, TestSet, ExpectedOutput, load_test_set,
        Runner, Score, CaseResult, RunResult,
        Scorer, DefaultScorer,
        ConsoleReporter,
    )
    import evalite
    assert set(evalite.__all__) == {
        "AgentAdapter", "AgentResponse", "sync_adapter",
        "TestCase", "TestSet", "ExpectedOutput", "load_test_set",
        "Runner", "Score", "CaseResult", "RunResult",
        "Scorer", "DefaultScorer",
        "ConsoleReporter",
    }
