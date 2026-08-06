from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ChatMessage:
    role: str
    content: str


@dataclass
class ChatRequest:
    messages: List[ChatMessage]

    temperature: float = 0.8
    max_tokens: int = 10000
    stream: bool = False

    stop: Optional[List[str]] = None

    @classmethod
    def from_json(cls, data: dict):

        messages = [
            ChatMessage(
                role=m.get("role", "user"),
                content=m.get("content", "")
            )
            for m in data.get("messages", [])
        ]

        return cls(
            messages=messages,
            temperature=data.get("temperature", 0.8),
            max_tokens=data.get("max_tokens", 10000),
            stream=data.get("stream", False),
            stop=data.get("stop")
        )
