from dataclasses import dataclass
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

    top_p: float = 1.0

    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0

    stop: Optional[List[str]] = None

    seed: Optional[int] = None

    user: Optional[str] = None

    @classmethod
    def from_json(cls, data: dict):

        messages = [
            ChatMessage(
                role=m.get("role", "user"),
                content=m.get("content", "")
            )
            for m in data.get("messages", [])
        ]

        stop = data.get("stop")

        if isinstance(stop, str):
            stop = [stop]

        return cls(
            messages=messages,

            temperature=float(data.get("temperature", 0.8)),

            max_tokens=int(
                data.get(
                    "max_tokens",
                    data.get("max_completion_tokens", 10000)
                )
            ),

            stream=bool(data.get("stream", False)),

            top_p=float(data.get("top_p", 1.0)),

            presence_penalty=float(
                data.get("presence_penalty", 0.0)
            ),

            frequency_penalty=float(
                data.get("frequency_penalty", 0.0)
            ),

            stop=stop,

            seed=data.get("seed"),

            user=data.get("user")
        )
