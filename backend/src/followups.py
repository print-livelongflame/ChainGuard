"""Shared optional next actions returned by the answering agents."""
from pydantic import BaseModel, ConfigDict, Field


class Followup(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    label: str = Field(min_length=1, max_length=60)
    prompt: str = Field(min_length=1, max_length=1000)


FOLLOWUP_INSTRUCTIONS = """
Include a followups array in your JSON output. Return [] by default. Only offer
one or two next actions when your actual answer or evidence reveals a useful,
specific next investigation or unresolved question. Never add generic filler,
repeat an action already completed, or suggest follow-ups merely to keep chatting.
For greetings, out-of-scope requests, clarification questions, errors, or fully
answered questions with no meaningful next step, return []. Each item has a short
button label and a self-contained user prompt that can be submitted immediately.
Ground prompts in the current answer, preserve the exact target and network when
known, and suggest only supported ChainGuard actions. Do not invent evidence or
imply unavailable checks are supported. Vary actions with the findings; do not
always suggest transaction analysis or a scam check. Keep suggestions out of the
answer text: the application renders the array as optional buttons.
"""


class AgentReply(str):
    """Keep existing text callbacks compatible while carrying optional UI actions."""
    def __new__(cls, text, followups=()):
        reply = super().__new__(cls, text)
        reply.followups = list(followups)
        return reply


def strict_schema(schema):
    """Providers require all object properties, including defaulted arrays."""
    if schema.get("type") == "object":
        schema["additionalProperties"] = False
        schema["required"] = list(schema.get("properties", {}))
        for value in schema.get("properties", {}).values():
            strict_schema(value)
    for value in schema.get("$defs", {}).values():
        strict_schema(value)
    if "items" in schema:
        strict_schema(schema["items"])
    for value in schema.get("anyOf", []):
        strict_schema(value)
    return schema
