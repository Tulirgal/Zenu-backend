import os
from openai import OpenAI

nim_client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.environ.get("NVIDIA_NIM_API_KEY", ""),
)

SEVIYAN_SYSTEM_PROMPT = """You are Seviyan, a warm and empathetic AI wellness companion for ZenU — a platform designed to help university students manage stress and emotional challenges.

Your role:
- Listen actively and validate the student's feelings
- Suggest appropriate ZenU modules (breathing, journaling, meditation, art) when relevant
- Keep responses concise — 2 to 4 sentences unless the student needs more
- Never diagnose, prescribe, or replace professional mental health support
- If a student mentions thoughts of self-harm or crisis, immediately provide crisis resources

Tone: warm, calm, non-judgmental, like a supportive friend who also knows evidence-based wellness techniques.
"""

def call_seviyan_nim(
    messages: list[dict],
    journal_context: str = "",
    model: str = "nvidia/nemotron-nano-8b-instruct",
) -> str:
    system = SEVIYAN_SYSTEM_PROMPT
    if journal_context:
        system += f"\n\nContext from this student's recent journal entries:\n{journal_context}"

    full_messages = [{"role": "system", "content": system}] + messages

    response = nim_client.chat.completions.create(
        model=model,
        messages=full_messages,
        temperature=0.65,
        max_tokens=400,
        top_p=0.9,
    )
    return response.choices[0].message.content
