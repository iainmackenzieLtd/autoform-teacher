"""
Field Explainer — uses Claude to explain what a form field is asking for.
"""

import anthropic
from dotenv import load_dotenv

load_dotenv()

_client = anthropic.Anthropic()


def explain_field(label: str) -> str:
    """Return a plain English sentence explaining what this form field wants."""
    message = _client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=150,
        messages=[{
            "role": "user",
            "content": (
                f"A job application form has a field labelled '{label}'. "
                "In one plain English sentence, explain what information "
                "this field is asking for. Be specific and practical."
            )
        }]
    )
    return message.content[0].text
