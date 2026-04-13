"""Entry point for end-to-end tests — starts FastAPI with a FakeRegistry
installed so Playwright tests don't need HuggingFace models or Ollama.

Usage (called by Playwright's `webServer` config):
    python run_test_server.py

Port 8001 is used by default to avoid colliding with a dev backend on :8000.
"""
from __future__ import annotations

import os

import uvicorn

# Install the fake registry BEFORE importing app.main (lifespan fires on
# startup and reads the registry at that moment).
from tests.conftest import FakeRegistry  # noqa: E402
from app import deps  # noqa: E402

_fake = FakeRegistry()
deps.set_test_registry(_fake)

# Also monkey-patch OllamaRewriter so the humanize endpoint doesn't need a
# live Ollama.  Mirrors the per-test patches in conftest, applied globally.
from app.humanizer import rewriter as rewriter_mod  # noqa: E402


async def _fake_check_available(self):
    return True


async def _fake_list_models(self):
    return ["fake-model:latest"]


async def _fake_rewrite(self, text, **kwargs):
    # Simple deterministic "humanization" for UI tests — strips a couple of
    # AI-markers so we can assert the humanized text is different.
    return (
        text.replace("Moreover, ", "").replace("Furthermore, ", "").replace(
            "it is important to note that ", ""
        )
    )


rewriter_mod.OllamaRewriter.check_available = _fake_check_available
rewriter_mod.OllamaRewriter.list_models = _fake_list_models
rewriter_mod.OllamaRewriter.rewrite = _fake_rewrite


if __name__ == "__main__":
    port = int(os.environ.get("AI_HUMANIZER_TEST_PORT", "8001"))
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, log_level="warning")
