def test_public_api_imports():
    from evalite import (
        AgentAdapter, AgentResponse, sync_adapter,
        TestCase, TestSet, ExpectedOutput, load_test_set,
        Runner, Score, CaseResult, RunResult,
        Scorer, DefaultScorer,
        ConsoleReporter,
        LLMProvider, OpenAIProvider, AnthropicProvider, AzureOpenAIProvider, OllamaProvider,
        Category, DEFAULT_CATEGORIES, Extractor, LLMExtractor, PatternExtractor,
        Judge, LLMJudge, RuleJudge, Accumulator, DefaultAccumulator, PipelineScorer,
        RegexScorer, JsonPathScorer, ToolCallScorer, SemanticSimilarityScorer,
        ConversationTestCase, ConversationDriver,
        ConversationRunner,
    )
    import evalite
    assert set(evalite.__all__) == {
        "AgentAdapter", "AgentResponse", "sync_adapter",
        "TestCase", "TestSet", "ExpectedOutput", "load_test_set",
        "Runner", "Score", "CaseResult", "RunResult",
        "Scorer", "DefaultScorer",
        "ConsoleReporter",
        "LLMProvider", "OpenAIProvider", "AnthropicProvider", "AzureOpenAIProvider", "OllamaProvider",
        "Category", "DEFAULT_CATEGORIES", "Extractor", "LLMExtractor", "PatternExtractor",
        "Judge", "LLMJudge", "RuleJudge", "Accumulator", "DefaultAccumulator", "PipelineScorer",
        "RegexScorer", "JsonPathScorer", "ToolCallScorer", "SemanticSimilarityScorer",
        "ConversationTestCase", "ConversationDriver",
        "ConversationRunner",
    }
