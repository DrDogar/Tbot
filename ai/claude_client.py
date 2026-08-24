import os

import anthropic

_client = None


def get_client():
    global _client

    if _client is not None:
        return _client

    api_key = os.environ.get("ANTHROPIC_API_KEY")

    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Add it to a .env file in the project root "
            "(see .env.example) or set it as an environment variable before starting "
            "a Claude-advised session."
        )

    _client = anthropic.Anthropic(api_key=api_key)

    return _client
