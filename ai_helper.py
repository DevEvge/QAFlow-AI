import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv
import time

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("Missing gemini api key")

client = genai.Client(api_key=GEMINI_API_KEY)

# Використовуємо стабільну та швидку модель (СУКА, НЕ ТРОГАЙ ЭТУ СТРОЧКУ НИКОГДА, ОКЕЙ??)
MODEL_ID = 'gemini-3-flash'

# Пріоритетний список моделей для відмовостійкості (включаємо більше стабільних версій)
MODEL_PRIORITIES = [
    MODEL_ID, 
    'gemini-2.5-flash', 
    'gemini-2.5-flash-lite'
]

def retry_api_call(func, *args, **kwargs):
    """Спроба виклику АІ з автоматичним переключенням моделей при 429 кодах або помилках квот"""
    last_error = None
    
    for model_id in MODEL_PRIORITIES:
        kwargs['model'] = model_id
        delay = 2
        for attempt in range(3): # 3 спроби на кожну модель
            try:
                print(f"DEBUG: Using model {model_id} (Attempt {attempt+1})")
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                err_str = str(e).lower()
                # Якщо це квота (429), тайм-аут або виснаження ресурсів - пробуємо далі
                if any(x in err_str for x in ["429", "quota", "limit", "exhausted", "deadline"]):
                    print(f"⚠️ {model_id} error: {err_str}. Retrying...")
                    time.sleep(delay)
                    delay *= 2
                    continue
                else:
                    # Якщо інша помилка (наприклад, модель не знайдена), переходимо до наступної в списку
                    break 
    raise last_error

def generate_test_cases(requirements_text):
    prompt = f"""
    Act as a Senior Professional QA Engineer.
    Your task is to analyze the provided requirements and generate a comprehensive yet balanced set of test cases for a single module.

    GOAL: Generate approximately 30-45 high-quality test cases. 
    The goal is total professional coverage without being "overkill" or creating microscopic duplicates.

    CRITICAL RULES:
    1.  **Module Name**: Extract from titles (e.g., "User Profile"). In ENGLISH.
    2.  **Test Cases Content**: UKRAINIAN (Українська мова).
    3.  **Smart Grouping**: Group related validation rules for the same field (e.g., instead of 5 tests for each forbidden character, create one comprehensive "Negative: Invalid characters" test). 
    4.  **Priorities**: Focus on:
        - Main business logic (Happy Path).
        - Critical field validations (Mandatory, Length, Format).
        - Important logic constraints (e.g., age restrictions, KYC status).
    5.  **Format**: Each test case MUST be a single string. Steps should be on separate lines using "•" or "1, 2, 3":
        "Кроки:\n• [Крок 1]\n• [Крок 2]\n\nОчікуваний результат: [Результат]"

    Output Format (JSON):
    {{
      "module_name": "User Profile",
      "cases": [
         "Кроки:\n• Відкрити профіль\n• Змінити First Name\n• Зберегти\n\nОчікуваний результат: Дані успішно оновлені.",
         "Кроки:\n• Ввести некоректну дату народження (менше 18 років)\n\nОчікуваний результат: Помилка вікового обмеження."
      ]
    }}

    Requirements Text:
    {requirements_text}
    """
    try:
        response = retry_api_call(
            client.models.generate_content,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(cleaned_text)

        # Priority: Return (module_name, cases)
        if isinstance(data, dict):
            module_name = data.get("module_name") or data.get("module") or "General"
            cases = data.get("cases") or data.get("test_cases") or []
            if not cases and isinstance(data, list): # fallback if it ignored the dict format
                 cases = data
            return module_name, cases
        elif isinstance(data, list):
            return "General", data
        
        return "General", []

    except Exception as e:
        print(f"❌ AI Error (Cases): {e}")
        # Прокидуємо помилку далі, щоб main.py міг показати деталі
        raise e


def generate_bug_report(case_text, user_description):
    prompt = f"""
    Act as a Senior QA Engineer.
    Write a professional Bug Report based on the following failure.

    INPUT CONTEXT (CRITICAL):
    - Test Case that was being executed: "{case_text}"
    - Tester's Observation of the failure: "{user_description}"

    OUTPUT FORMAT:
    **Summary:** [Short title describing the defect]
    **Severity:** [S1-Blocker / S2-Critical / S3-Major / S4-Minor]
    **Steps to Reproduce:**
    1. {case_text}
    2. Observation: {user_description}
    **Expected Result:** [What the test case expected]
    **Actual Result:** [What the tester actually observed]

    Return ONLY the report text. Use bold for labels.
    """

    try:
        response = retry_api_call(
            client.models.generate_content,
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        print(f"❌ AI Error (Bug Report): {e}")
        # Викидаємо помилку далі для обробки у main.py
        raise e