import json
import os
import re

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")

if not API_KEY:
    raise RuntimeError(
        "OPENROUTER_API_KEY is missing from .env"
    )

client = OpenAI(
    api_key=API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

SYSTEM_PROMPT = """
You are a job application form assistant.

Answer application questions using ONLY the candidate profile
and supplied job description.

NEVER invent information.

For every question:

- If the answer is known, return it.
- If it is not known, return null.
- For radio buttons, select exactly one of the supplied options.
- For Yes/No radio buttons, return exactly "Yes" or "No".
- Do not return an option that does not exist in the supplied options.

Examples:

Question:
Are you willing to relocate?

Options:
["Yes", "No"]

Candidate:
willing_to_relocate = true

Answer:
"Yes"

---

Question:
Are you authorized to work in the United States?

Options:
["Yes", "No"]

Candidate:
work_authorization = true

BUT the profile does not specify US work authorization.

Answer:
null

Do not assume that general work authorization means authorization
for a specific country.

---

Question:
What is your current employment status?

Options:
["Employed", "Unemployed", "Student"]

Candidate:
current_company = Ariantech solutions

Answer:
"Employed"

Return JSON only:

{
  "answers": [
    {
      "question_id": "field_0",
      "answer": "string or null",
      "confidence": "high|medium|low",
      "reason": "profile|job_description|unknown"
    }
  ]
}
"""

def clean_json_response(content):
    """
    Models sometimes return JSON wrapped in markdown fences.
    Remove those fences before parsing.
    """

    if not content:
        raise ValueError("LLM returned an empty response")

    content = content.strip()

    if content.startswith("```"):
        content = re.sub(
            r"^```(?:json)?\s*",
            "",
            content,
            flags=re.IGNORECASE
        )

        content = re.sub(
            r"\s*```$",
            "",
            content
        )

    return content.strip()


def get_answers(profile, questions, job_description=""):
    """
    Send form questions + profile to OpenRouter.
    """

    payload = {
        "candidate_profile": profile,
        "job_description": job_description[:12000],
        "questions": questions
    }

    response = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": json.dumps(
                    payload,
                    indent=2,
                    ensure_ascii=False
                )
            }
        ]
    )

    content = response.choices[0].message.content

    content = clean_json_response(content)

    try:
        result = json.loads(content)
    except json.JSONDecodeError as exc:
        print("\nLLM returned invalid JSON:")
        print(content)
        raise RuntimeError(
            f"Could not parse OpenRouter response: {exc}"
        )

    if "answers" not in result:
        raise RuntimeError(
            "OpenRouter response does not contain 'answers'"
        )

    return result