"""Shared pytest options for backend tests."""


def pytest_addoption(parser):
    parser.addoption(
        "--exclude",
        action="append",
        default=[],
        metavar="PROVIDERS",
        help=(
            "exclude provider(s) from the live LLM token benchmark; "
            "comma-separated names are accepted (openai, gemini, claude)"
        ),
    )
