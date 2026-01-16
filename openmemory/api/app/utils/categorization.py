import logging
import os
from typing import List

from app.utils.prompts import MEMORY_CATEGORIZATION_PROMPT
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()


class MemoryCategories(BaseModel):
    categories: List[str]


def _is_mistral():
    """Check if we're using Mistral API."""
    base_url = os.getenv("OPENAI_BASE_URL", "")
    return "mistral.ai" in base_url


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=15))
def get_categories_for_memory(memory: str) -> List[str]:
    try:
        messages = [
            {"role": "system", "content": MEMORY_CATEGORIZATION_PROMPT},
            {"role": "user", "content": memory}
        ]

        if _is_mistral():
            # Use Mistral's structured output API
            from mistralai import Mistral
            client = Mistral(api_key=os.getenv("OPENAI_API_KEY"))
            completion = client.chat.parse(
                model=os.getenv("MISTRAL_MODEL", "mistral-medium-latest"),
                messages=messages,
                response_format=MemoryCategories,
                temperature=0
            )
        else:
            # Use OpenAI's structured output API
            openai_client = OpenAI()
            completion = openai_client.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=messages,
                response_format=MemoryCategories,
                temperature=0
            )

        parsed: MemoryCategories = completion.choices[0].message.parsed
        return [cat.strip().lower() for cat in parsed.categories]

    except Exception as e:
        logging.error(f"[ERROR] Failed to get categories: {e}")
        try:
            logging.debug(f"[DEBUG] Raw response: {completion.choices[0].message.content}")
        except Exception as debug_e:
            logging.debug(f"[DEBUG] Could not extract raw response: {debug_e}")
        raise
