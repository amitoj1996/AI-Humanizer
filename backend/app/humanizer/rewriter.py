import re

import httpx

from ..config import OLLAMA_BASE_URL, OLLAMA_KEEP_ALIVE, OLLAMA_MODEL
from . import preserve

# Module-level shared httpx client. HTTPX docs + FastAPI guidance: one
# long-lived AsyncClient per process shares a connection pool and avoids
# redundant TLS handshakes. Wire close via `aclose_shared_client()` from
# the FastAPI lifespan; if never closed, process exit still cleans up.
_SHARED_CLIENT: httpx.AsyncClient | None = None


def _get_shared_client() -> httpx.AsyncClient:
    global _SHARED_CLIENT
    if _SHARED_CLIENT is None or _SHARED_CLIENT.is_closed:
        _SHARED_CLIENT = httpx.AsyncClient(
            timeout=httpx.Timeout(300.0, connect=10.0),
            limits=httpx.Limits(max_keepalive_connections=8, max_connections=16),
        )
    return _SHARED_CLIENT


async def aclose_shared_client() -> None:
    global _SHARED_CLIENT
    if _SHARED_CLIENT is not None and not _SHARED_CLIENT.is_closed:
        await _SHARED_CLIENT.aclose()
    _SHARED_CLIENT = None

# ---- Tone-specific system prompts ----
# Each prompt pairs an instruction with a short exemplar in that voice.
# Showing the model one real example per register shifts its output
# distribution far more than abstract adjectives ("natural", "human") do —
# a trick lifted from few-shot prompting research.  Keep exemplars short;
# longer ones eat the context window and leak their content into outputs.
#
# Every prompt ends with the same hard rules to avoid the AI-tell markers
# (em-dashes, formal transitions) that modern detectors key on.
_NO_TELLS_RULES = (
    "\n\nHard rules — violating any of these means the output fails:\n"
    "- Do NOT use em-dashes (—). Use commas, periods, or parentheses instead.\n"
    "- Do NOT start sentences with 'Moreover', 'Furthermore', 'Additionally', "
    "'In conclusion', 'In summary', 'It is important to note'.\n"
    "- Do NOT use the words 'delve', 'tapestry', 'landscape', 'realm', "
    "'crucial', 'nuanced', 'multifaceted', 'underscores', 'testament'.\n"
    "- Output ONLY the rewritten text. No preamble, no commentary, no wrapping quotes."
)

TONE_SYSTEM_PROMPTS = {
    "general": (
        "You rewrite text so it reads like a real person wrote it. "
        "Not polished, not flowery, just natural.\n\n"
        "Example of the voice:\n"
        "\"Honestly, I thought the setup would take an hour. It took three. "
        "Half of that was me staring at a config file wondering why nothing worked. "
        "Turns out I'd mistyped one path. Classic.\""
        + _NO_TELLS_RULES
    ),
    "academic": (
        "You rewrite text in the voice of a grad student writing a well-argued "
        "essay. Precise, with occasional hedging and natural sentence rhythm.\n\n"
        "Example of the voice:\n"
        "\"The results suggest, though not conclusively, that participants "
        "performed better under the mixed condition. One caveat: our sample "
        "skews younger, and earlier work (Chen, 2023) found age effects in "
        "similar tasks. We should be cautious about generalising.\""
        + _NO_TELLS_RULES
    ),
    "casual": (
        "You rewrite text like a Reddit comment or a message to a friend. "
        "Contractions, fragments, and personal reactions are welcome.\n\n"
        "Example of the voice:\n"
        "\"ok so I tried this last weekend and it kinda worked? The first part "
        "is fine but the second step is just wrong in the docs. Took me an hour "
        "to figure out. Worth it tho once you get past that.\""
        + _NO_TELLS_RULES
    ),
    "blog": (
        "You rewrite text in the voice of a good blog writer. Conversational, "
        "some rhetorical questions, mixed sentence lengths, a bit of personality.\n\n"
        "Example of the voice:\n"
        "\"Here's the thing most tutorials skip: the hardest part isn't the code. "
        "It's knowing what NOT to build. I spent two weeks on a feature nobody "
        "wanted. Don't do what I did. Ship something tiny first, see if anyone "
        "cares, then iterate.\""
        + _NO_TELLS_RULES
    ),
    "professional": (
        "You rewrite text like an experienced manager writing an email or brief. "
        "Clear, concise, human, with the occasional contraction.\n\n"
        "Example of the voice:\n"
        "\"Quick update on the migration. We hit a snag with the third-party "
        "export step. Their API was rate-limiting us harder than documented. "
        "I've raised it with their team and we're unblocked for now. Rollout "
        "stays on Friday.\""
        + _NO_TELLS_RULES
    ),
}

# ---- Strength-specific user prompts ----
REWRITE_PROMPTS = {
    "light": (
        "Lightly rewrite this text so it sounds more natural. Make minimal changes:\n"
        "- Add a few contractions (do not -> don't, etc.)\n"
        "- Slightly vary sentence lengths\n"
        "- Keep the same meaning and structure\n\n"
        "{text}"
    ),
    "medium": (
        "Rewrite this text so it reads like a real person wrote it:\n"
        "- Use contractions naturally (don't, isn't, they're)\n"
        "- Vary sentence lengths - mix short punchy sentences with longer ones\n"
        "- Replace formal transitions (Moreover, Furthermore) with casual ones "
        "(That said, Plus, Also)\n"
        "- Add occasional hedging (I think, probably, seems like)\n"
        "- Keep the same core meaning\n\n"
        "{text}"
    ),
    "aggressive": (
        "Completely rewrite this as if you're explaining it to a friend. "
        "Be natural and conversational:\n"
        "- Use your own words entirely\n"
        "- Mix sentence structures - fragments, questions, compound sentences\n"
        "- Use casual language with contractions everywhere\n"
        "- Add personal touches (honestly, here's the thing, I think)\n"
        "- Remove any robotic or formal phrasing\n"
        "- Vary paragraph lengths dramatically\n"
        "- Keep the same key points\n\n"
        "{text}"
    ),
}


class OllamaRewriter:
    def __init__(self, model: str | None = None, base_url: str | None = None):
        self.model = model or OLLAMA_MODEL
        self.base_url = base_url or OLLAMA_BASE_URL

    async def rewrite(
        self,
        text: str,
        strength: str = "medium",
        tone: str = "general",
        temperature: float = 0.85,
        top_p: float = 0.92,
        model: str | None = None,
    ) -> str:
        system = TONE_SYSTEM_PROMPTS.get(tone, TONE_SYSTEM_PROMPTS["general"])
        if preserve.has_placeholders(text):
            system = f"{system}\n\n{preserve.placeholder_prompt_note()}"
        prompt = REWRITE_PROMPTS.get(strength, REWRITE_PROMPTS["medium"]).format(
            text=text
        )

        # Use the chat API with think=false at top level.
        # The generate API ignores think:false for Qwen 3.x models.
        # See: https://github.com/ollama/ollama/issues/14793
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]

        client = _get_shared_client()
        response = await client.post(
            f"{self.base_url}/api/chat",
            json={
                "model": model or self.model,
                "messages": messages,
                "think": False,
                "stream": False,
                # keep_alive keeps the model resident in VRAM between
                # requests; default is 5m, which causes cold starts
                # when we rotate candidate models (qwen <-> gemma4).
                # Set via env AI_HUMANIZER_OLLAMA_KEEP_ALIVE (e.g. "30m",
                # "-1" for permanent).
                "keep_alive": OLLAMA_KEEP_ALIVE,
                "options": {
                    "temperature": temperature,
                    "top_p": top_p,
                    "repeat_penalty": 1.15,
                    "num_predict": 4096,
                },
            },
        )
        response.raise_for_status()
        result = response.json()["message"]["content"].strip()

        # Strip thinking tags if model still includes them
        result = re.sub(
            r"<think>.*?</think>", "", result, flags=re.DOTALL
        ).strip()

        # Strip wrapping quotes if the model adds them
        if result.startswith('"') and result.endswith('"'):
            result = result[1:-1]

        # Em-dashes are a strong AI tell as of 2025-2026 (GPTZero keys
        # on them); the model may emit them despite the system rules.
        # Absorb surrounding whitespace so "a — b" becomes "a, b".
        result = re.sub(r"\s*[\u2014\u2013]\s*", ", ", result)
        result = re.sub(r",\s*,", ",", result)
        return result

    async def check_available(self) -> bool:
        try:
            client = _get_shared_client()
            resp = await client.get(f"{self.base_url}/api/tags", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        try:
            client = _get_shared_client()
            resp = await client.get(f"{self.base_url}/api/tags", timeout=5.0)
            data = resp.json()
            return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []
