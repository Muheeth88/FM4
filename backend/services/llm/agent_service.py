import json
import logging
import os
import re
from typing import Any, Dict, Optional, Sequence

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


class BaseLLMAgentService:
    """Reusable LangChain agent wrapper for OpenAI-backed tasks."""

    def __init__(
        self,
        system_prompt: str,
        tools: Optional[Sequence[Any]] = None,
        model: Optional[str] = None,
        temperature: float = 0,
        max_retries: int = 2,
        timeout: Optional[int] = 60,
        verbose: bool = False,
    ):
        self.system_prompt = system_prompt
        self.tools = list(tools or [])
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        self.temperature = temperature
        self.max_retries = max_retries
        self.timeout = timeout
        self.verbose = verbose
        self._agent = None

    def is_enabled(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY"))

    def invoke(self, user_input: str) -> str:
        if not self.is_enabled():
            raise RuntimeError("OPENAI_API_KEY is not configured")

        agent = self._get_agent()
        response = agent.invoke({
            "messages": [
                {"role": "user", "content": user_input}
            ]
        })
        return self._extract_output(response)

    def invoke_json(self, user_input: str) -> Any:
        raw_output = self.invoke(user_input)
        return self._parse_json_output(raw_output)

    def _get_agent(self):
        if self._agent is None:
            llm = ChatOpenAI(
                model=self.model,
                temperature=self.temperature,
                max_retries=self.max_retries,
                timeout=self.timeout,
            )
            self._agent = create_agent(
                model=llm,
                tools=self.tools,
                system_prompt=self.system_prompt,
                debug=self.verbose,
            )
        return self._agent

    @staticmethod
    def _extract_output(response: Any) -> str:
        if isinstance(response, dict):
            structured_response = response.get("structured_response")
            if structured_response is not None:
                if isinstance(structured_response, str):
                    return structured_response
                return json.dumps(structured_response)

            messages = response.get("messages", [])
            for message in reversed(messages):
                content = getattr(message, "content", None)
                if isinstance(content, str) and content.strip():
                    return content
                if isinstance(content, list):
                    parts = []
                    for item in content:
                        if isinstance(item, str):
                            parts.append(item)
                        elif isinstance(item, dict):
                            text = item.get("text") or item.get("content")
                            if text:
                                parts.append(text)
                    if parts:
                        return "\n".join(parts)

            output = response.get("output")
            if isinstance(output, str):
                return output

        return str(response)

    @staticmethod
    def _parse_json_output(raw_output: str) -> Any:
        candidate = raw_output.strip()

        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, (dict, list)):
                return parsed
        except json.JSONDecodeError:
            pass

        match = re.search(r"(\{.*\}|\[.*\])", candidate, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, (dict, list)):
                    return parsed
            except json.JSONDecodeError:
                logger.warning("Failed to parse JSON payload from LLM output")

        raise ValueError("LLM output was not valid JSON")
