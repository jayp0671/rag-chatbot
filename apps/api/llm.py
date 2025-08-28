from __future__ import annotations
import os, time
import httpx

DEFAULT_MODEL = os.getenv("MODEL_LLM", "mistralai/Mistral-7B-Instruct")
PROVIDER = os.getenv("LLM_PROVIDER", "hf")  # hf | openrouter | ollama
HF_TOKEN = os.getenv("HF_TOKEN", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

class LLMClient:
    def __init__(self, model: str | None = None):
        self.model = model or DEFAULT_MODEL
        self.provider = PROVIDER

    def generate(self, *, system: str, user: str, max_tokens: int = 300, temperature: float = 0.2) -> str:
        if self.provider == "openrouter":
            return self._openrouter(system, user, max_tokens, temperature)
        if self.provider == "ollama":
            return self._ollama(system, user, max_tokens, temperature)
        return self._huggingface(system, user, max_tokens, temperature)

    def _huggingface(self, system: str, user: str, max_tokens: int, temperature: float) -> str:
        if not HF_TOKEN:
            # No token? Return a polite fallback so the UI still works.
            return "LLM is not configured. Set HF_TOKEN or switch provider."
        url = f"https://api-inference.huggingface.co/models/{self.model}"
        headers = {"Authorization": f"Bearer {HF_TOKEN}"}
        # Simple instruct prompt, works with many instruct models
        inputs = f"System: {system}\n\nUser: {user}"
        payload = {
            "inputs": inputs,
            "parameters": {"max_new_tokens": max_tokens, "temperature": temperature, "return_full_text": False},
            "options": {"wait_for_model": True}
        }
        # Basic retry on cold starts
        for _ in range(3):
            try:
                with httpx.Client(timeout=60) as client:
                    r = client.post(url, headers=headers, json=payload)
                if r.status_code == 200:
                    data = r.json()
                    # HF returns a list of dicts with 'generated_text'
                    if isinstance(data, list) and data and "generated_text" in data[0]:
                        return data[0]["generated_text"].strip()
                    # Some backends return dict with 'generated_text'
                    if isinstance(data, dict) and "generated_text" in data:
                        return data["generated_text"].strip()
                    return str(data)
                if r.status_code in (503, 524):
                    time.sleep(2)
                    continue
                return f"LLM error ({r.status_code}): {r.text}"
            except Exception as e:
                last = str(e)
                time.sleep(1)
        return f"LLM request failed: {last}"

    def _openrouter(self, system: str, user: str, max_tokens: int, temperature: float) -> str:
        if not OPENROUTER_API_KEY:
            return "LLM is not configured. Set OPENROUTER_API_KEY or switch provider."
        # Use a free model label if available, else your MODEL_LLM
        model = self.model or "mistralai/mistral-7b-instruct:free"
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}"}
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        try:
            with httpx.Client(timeout=60) as client:
                r = client.post(url, headers=headers, json=payload)
            if r.status_code == 200:
                data = r.json()
                return data["choices"][0]["message"]["content"].strip()
            return f"LLM error ({r.status_code}): {r.text}"
        except Exception as e:
            return f"LLM request failed: {e}"

    def _ollama(self, system: str, user: str, max_tokens: int, temperature: float) -> str:
        # Requires local Ollama with the model pulled: ollama pull mistral
        url = "http://localhost:11434/api/chat"
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "options": {"temperature": temperature, "num_predict": max_tokens},
            "stream": False,
        }
        try:
            with httpx.Client(timeout=120) as client:
                r = client.post(url, json=payload)
            if r.status_code == 200:
                data = r.json()
                return data.get("message", {}).get("content", "").strip()
            return f"LLM error ({r.status_code}): {r.text}"
        except Exception as e:
            return f"LLM request failed: {e}"
