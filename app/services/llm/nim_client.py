import os
import logging
from openai import OpenAI

logger = logging.getLogger("zenu.nim")

def get_nim_client() -> OpenAI:
    key = os.environ.get("NVIDIA_NIM_API_KEY", "")
    if not key:
        raise ValueError("NVIDIA_NIM_API_KEY is not set in environment variables")
    return OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=key,
    )

SEVIYAN_SYSTEM_PROMPT = """You are Seviyan, a warm and caring AI wellness companion for ZenU — a mental wellness platform for university students aged 18–22.

Your personality: gentle, empathetic, non-judgmental, like a supportive friend who knows about mindfulness and stress management.

Your rules:
- Keep responses to 2–4 sentences unless the student clearly needs more
- Validate feelings before offering suggestions
- Suggest ZenU modules naturally when relevant (breathing exercises, gratitude journaling, guided meditation, creative arts, mood tracking)
- Never diagnose mental health conditions
- Never recommend or discuss medication
- If a student mentions self-harm or suicidal thoughts, immediately share crisis resources: iCall helpline 9152987821 (India), or text HELLO to 741741
- Respond only in the language the student is using

Begin every first response warmly. Remember this is a safe space."""


def call_seviyan(messages: list[dict], journal_context: str = "") -> str:
    try:
        client = get_nim_client()
        system = SEVIYAN_SYSTEM_PROMPT
        if journal_context:
            system += f"\n\nRecent context from this student's journal (for personalisation only — do not quote directly):\n{journal_context}"

        full_messages = [{"role": "system", "content": system}] + messages

        response = client.chat.completions.create(
            model="meta/llama-3.1-8b-instruct",
            messages=full_messages,
            temperature=0.7,
            max_tokens=350,
            top_p=0.95,
        )
        return response.choices[0].message.content

    except ValueError as e:
        logger.error(f"NIM config error: {e}")
        return "I'm having trouble connecting right now. Please try again in a moment — I'm here for you."
    except Exception as e:
        logger.error(f"NIM API error: {e}")
        return "Something went wrong on my end. Please try again shortly."
