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
    print(f"🤖 Відправляю в AI текст вимог...")
    prompt = f"""
    Act as a Senior QA Engineer. 
    Analyze the following requirements text and extract checklist-style test cases.

    Requirements:
    {requirements_text}

    OUTPUT FORMAT RULES:
    1. Return ONLY a raw JSON list of strings. No markdown, no "json" tags.
    2. Example: ["Verify login", "Check validation"]
    3. Language: Ukrainian.
    """
    try:
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt
        )
        text = response.text.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception as e:
        print(f"❌ Помилка AI: {e}")
        return []


def generate_bug_report(case_text, user_description):
    """
    Генерує баг-репорт на основі кейсу та опису юзера.
    """
    print(f"🐛 Генерую баг-репорт...")

    prompt = f"""
    Act as a Senior QA Engineer.
    I found a bug while executing a test case. 
    Please write a professional, short, and clear Bug Report in English based on the inputs below.

    INPUT DATA:
    - Original Test Case: "{case_text}"
    - Tester's Observation (What went wrong): "{user_description}"

    OUTPUT FORMAT RULES:
    1. Language: English (Technical style).
    2. Structure:
       **Title:** [Concise summary of the bug]
       **Description:** [Short explanation]
       **Expected Result:** [What should happen based on the test case]
       **Actual Result:** [What actually happened based on observation]
    3. Do NOT add preamble or extra text. Just the bug report fields.
    """

    try:
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        print(f"❌ Помилка генерації баг-репорту: {e}")
        return f"Error generating report. Original desc: {user_description}"