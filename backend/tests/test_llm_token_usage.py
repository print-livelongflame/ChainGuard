"""Opt-in live benchmark comparing cloud-model token usage."""
import os
from collections import defaultdict
from time import perf_counter

import pytest
from rich.console import Console
from rich.table import Table

from src.llm_config import Assignments, LLMConfig
from src.llm_provider import (
    _PROVIDERS,
    complete_with_usage,
    provider_available,
    use_llm_settings,
)


PROMPTS = (
    "Who are you?",
    "what is rug pull?",
    "can u check if this token is a scam 0x906CC2Ad139eb6637e28605F908903C8aDCe566A?",
)
RUN_LIVE_BENCHMARK = os.getenv("CHAINGUARD_RUN_LLM_TOKEN_BENCHMARK") == "1"


@pytest.mark.skipif(
    not RUN_LIVE_BENCHMARK,
    reason="Set CHAINGUARD_RUN_LLM_TOKEN_BENCHMARK=1 to make billable model calls.",
)
def test_compare_cloud_model_token_usage(pytestconfig):
    excluded = {
        name.strip().casefold()
        for value in pytestconfig.getoption("--exclude")
        for name in value.split(",")
        if name.strip()
    }
    unknown = excluded - _PROVIDERS.keys()
    if unknown:
        pytest.fail(
            "Unknown provider(s) in --exclude: "
            + ", ".join(sorted(unknown))
            + ". Choose openai, gemini, or claude."
        )

    providers = tuple(provider for provider in _PROVIDERS if provider not in excluded)
    if not providers:
        pytest.fail("All providers were excluded; choose at least one model to benchmark.")

    missing = [provider for provider in providers if not provider_available(provider)]
    if missing:
        pytest.fail(
            "Configure API keys for every model before benchmarking: "
            + ", ".join(missing)
        )

    results = []
    for provider in providers:
        settings = LLMConfig(
            assignments=Assignments(
                business_analyser=provider,
                scam_checker=provider,
                forensic_investigator=provider,
            )
        )
        for prompt in PROMPTS:
            started = perf_counter()
            with use_llm_settings(settings):
                content, usage = complete_with_usage(
                    [{"role": "user", "content": prompt}],
                    temperature=0,
                )
            elapsed = perf_counter() - started
            if usage is None:
                pytest.fail(
                    f"{provider} did not return token usage for prompt {prompt!r}; "
                    "no token counts were estimated."
                )
            results.append(
                {
                    "provider": provider,
                    "model": _PROVIDERS[provider]["model"],
                    "prompt": prompt,
                    "usage": usage,
                    "seconds": elapsed,
                    "response_chars": len(content),
                }
            )

    details_table = Table(title="Token usage by prompt", show_lines=True)
    details_table.add_column("Model", style="cyan", no_wrap=True)
    details_table.add_column("Prompt", max_width=60)
    details_table.add_column("Input", justify="right")
    details_table.add_column("Output", justify="right")
    details_table.add_column("Total", justify="right", style="bold")
    details_table.add_column("Time (s)", justify="right")
    details_table.add_column("Response chars", justify="right")
    for result in results:
        usage = result["usage"]
        details_table.add_row(
            result["model"],
            result["prompt"],
            str(usage["input_tokens"]),
            str(usage["output_tokens"]),
            str(usage["total_tokens"]),
            f'{result["seconds"]:.2f}',
            str(result["response_chars"]),
        )
    Console().print(details_table)

    grouped = defaultdict(list)
    for result in results:
        grouped[result["model"]].append(result["usage"])
    average_table = Table(title="Average per prompt")
    average_table.add_column("Model", style="cyan", no_wrap=True)
    average_table.add_column("Input tokens", justify="right")
    average_table.add_column("Output tokens", justify="right")
    average_table.add_column("Total tokens", justify="right", style="bold")
    average_table.add_column("Avg. time (s)", justify="right")
    for model, usages in grouped.items():
        count = len(usages)
        durations = [
            result["seconds"] for result in results if result["model"] == model
        ]
        average_table.add_row(
            model,
            f'{sum(item["input_tokens"] for item in usages) / count:.1f}',
            f'{sum(item["output_tokens"] for item in usages) / count:.1f}',
            f'{sum(item["total_tokens"] for item in usages) / count:.1f}',
            f"{sum(durations) / len(durations):.2f}",
        )
    Console().print(average_table)
