"""Console reporter for evaluation results."""

from typing import Literal

from evalite.runner.result import RunResult


class ConsoleReporter:
    """Prints evaluation results to stdout in table or JSON format."""

    def report(
        self,
        result: RunResult,
        fmt: Literal["table", "json"] = "table",
    ) -> None:
        """Print evaluation results to stdout.

        Args:
            result: The evaluation run result to report.
            fmt: Output format - "table" for text table, "json" for JSON.
        """
        if fmt == "table":
            self._report_table(result)
        elif fmt == "json":
            print(result.model_dump_json(indent=2))

    def _report_table(self, result: RunResult) -> None:
        """Print results as a simple text table."""
        # Print header
        header = f"{'case_id':<20} {'iter':<5} {'passed':<7} {'score':<7} {'duration_ms':<10}"
        print(header)
        print("-" * len(header))

        # Print rows
        for case_result in result.case_results:
            case_id = case_result.case_id
            iteration = case_result.iteration
            passed = "True" if case_result.passed else "False"
            score = case_result.score.value
            duration_ms = case_result.duration_ms

            row = f"{case_id:<20} {iteration:<5} {passed:<7} {score:<7.2f} {duration_ms:<10.1f}"
            print(row)

        # Print footer
        if result.total == 0:
            pass_rate_pct = 0.0
        else:
            pass_rate_pct = result.pass_rate * 100

        footer = f"Passed: {result.passed}/{result.total} ({pass_rate_pct:.1f}%)"
        print(footer)
