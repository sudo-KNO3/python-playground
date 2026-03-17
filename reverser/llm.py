"""Configurable LLM backend for the reverser tool."""

import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = (
    "You are an expert software engineer and code analyst. "
    "Analyze code accurately and concisely."
)


class LLM:
    """Thin wrapper around multiple LLM backends."""

    def __init__(
        self,
        backend: str = "claude",
        ollama_host: Optional[str] = None,
        ollama_model: Optional[str] = None,
    ) -> None:
        """Initialize the LLM with the specified backend.

        Args:
            backend: One of 'claude', 'openai', 'ollama'.
            ollama_host: Override for Ollama host URL.
            ollama_model: Override for Ollama model name.
        """
        self.backend = backend
        self._client = None

        if backend == "claude":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY is not set. "
                    "Set it in your environment or .env file."
                )
            try:
                import anthropic

                self._client = anthropic.Anthropic(api_key=api_key)
            except ImportError:
                raise ImportError(
                    "anthropic package is required. Run: pip install anthropic"
                )
            self._model = os.getenv(
                "REVERSER_CLAUDE_MODEL", "claude-opus-4-5"
            )

        elif backend == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError(
                    "OPENAI_API_KEY is not set. "
                    "Set it in your environment or .env file."
                )
            try:
                import openai

                self._client = openai.OpenAI(api_key=api_key)
            except ImportError:
                raise ImportError(
                    "openai package is required. Run: pip install openai"
                )
            self._model = os.getenv("REVERSER_OPENAI_MODEL", "gpt-4o")

        elif backend == "ollama":
            try:
                import httpx  # noqa: F401 — just verify it's installed
            except ImportError:
                raise ImportError(
                    "httpx package is required. Run: pip install httpx"
                )
            self._ollama_host = (
                ollama_host
                or os.getenv("REVERSER_OLLAMA_HOST", "http://localhost:11434")
            )
            self._model = (
                ollama_model
                or os.getenv("REVERSER_OLLAMA_MODEL", "llama3")
            )
        else:
            raise ValueError(
                f"Unknown backend '{backend}'. "
                "Choose from: claude, openai, ollama"
            )

    def complete(
        self, prompt: str, system: str = SYSTEM_PROMPT
    ) -> str:
        """Send a prompt and return the response text.

        Args:
            prompt: The user prompt.
            system: The system prompt (persona/instructions).

        Returns:
            The LLM response as a string.
        """
        if self.backend == "claude":
            return self._complete_claude(prompt, system)
        elif self.backend == "openai":
            return self._complete_openai(prompt, system)
        else:
            return self._complete_ollama(prompt, system)

    def _complete_claude(self, prompt: str, system: str) -> str:
        """Call the Anthropic API."""
        response = self._client.messages.create(  # type: ignore[union-attr]
            model=self._model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    def _complete_openai(self, prompt: str, system: str) -> str:
        """Call the OpenAI API."""
        response = self._client.chat.completions.create(  # type: ignore[union-attr]
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content or ""

    def _complete_ollama(self, prompt: str, system: str) -> str:
        """Call Ollama via HTTP."""
        import httpx

        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        try:
            resp = httpx.post(
                f"{self._ollama_host}/api/generate",
                json={
                    "model": self._model,
                    "prompt": full_prompt,
                    "stream": False,
                },
                timeout=120.0,
            )
            resp.raise_for_status()
        except httpx.ConnectError:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self._ollama_host}. "
                "Is Ollama running?"
            )
        return resp.json().get("response", "")
