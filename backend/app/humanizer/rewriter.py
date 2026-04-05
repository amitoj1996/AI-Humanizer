import re

import httpx

from ..config import OLLAMA_BASE_URL, OLLAMA_MODEL

# ---- Tone-specific system prompts ----
TONE_SYSTEM_PROMPTS = {
    "general": (
        "You are a text rewriter. You receive text and rewrite it to sound "
        "naturally human-written. Output ONLY the rewritten text — no commentary, "
        "no preamble, no quotation marks wrapping the result."
    ),
    "academic": (
        "You are an academic writer. Rewrite the text in a scholarly but natural "
        "tone — the kind a grad student would use in a well-written essay. "
        "Use varied vocabulary, some hedging (suggests, appears to, may), and "
        "occasional first-person where appropriate. Avoid robotic phrasing. "
        "Output ONLY the rewritten text."
    ),
    "casual": (
        "You are a casual writer. Rewrite the text like you're texting a friend "
        "or writing a Reddit comment. Use contractions, slang, short sentences, "
        "and personal opinions freely. Output ONLY the rewritten text."
    ),
    "blog": (
        "You are a blog writer. Rewrite the text in an engaging, conversational "
        "blog style — hook the reader, use rhetorical questions, mix short and "
        "long sentences, and include personality. Output ONLY the rewritten text."
    ),
    "professional": (
        "You are a professional business writer. Rewrite the text in a clear, "
        "polished but human tone — like an experienced manager writing an email "
        "or report. Use contractions sparingly, keep it concise, vary sentence "
        "structure. Output ONLY the rewritten text."
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
    ) -> str:
        system = TONE_SYSTEM_PROMPTS.get(tone, TONE_SYSTEM_PROMPTS["general"])
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

        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "think": False,
                    "stream": False,
                    "options": {
                        "temperature": 0.85,
                        "top_p": 0.92,
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
            return result

    async def check_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                data = resp.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []
