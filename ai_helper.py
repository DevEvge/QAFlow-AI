import os
import json
from google import genai
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("Missing gemini api key")

client = genai.Client(api_key=GEMINI_API_KEY)


def generate_test_cases(requirements_text):
    # Промпт тепер просить структуру {module_name, cases}
    prompt = f"""
    Act as a Senior QA Engineer. 
    Analyze the following requirements text.

    1. Generate a concise, professional Name for this Module (2-4 words) based on the content.
    2. Extract checklist-style test cases.

    Requirements:
    {requirements_text}

    OUTPUT FORMAT RULES:
    1. Return ONLY raw JSON. No markdown, no ```json``` tags.
    2. Structure:
    {{
        "module_name": "User Profile Settings",
        "cases": [
            "Verify that...",
            "Check that..."
        ]
    }}
    3. Language: Ukrainian.
    """
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=prompt
        )
        text_response = response.text.strip()
        # Чистимо від маркдауну, якщо AI його таки додав
        clear_json = text_response.replace("```json", "").replace("```", "").strip()

        data = json.loads(clear_json)

        # Перестраховка: якщо AI повернув просто список (старий формат), робимо заглушку
        if isinstance(data, list):
            return "Generated Module", data

        return data.get("module_name", "Unknown Module"), data.get("cases", [])

    except Exception as e:
        print(f"❌ Помилка AI (Cases): {e}")
        return None, []


def generate_bug_report(case_text, user_description):
    prompt = f"""
    Act as a Senior QA Engineer.
    I found a bug. Write a professional Bug Report in English.

    Test Case: "{case_text}"
    Observation: "{user_description}"

    OUTPUT FORMAT:
    **Title:** [Summary]
    **Description:** [Details]
    **Expected Result:** [Exp]
    **Actual Result:** [Act]

    Return ONLY the report text.
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        print(f"❌ Помилка AI (Bug Report): {e}")
        return f"Error generating report. Desc: {user_description}"