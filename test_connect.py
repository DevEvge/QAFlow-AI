import os

import gspread
from dotenv import load_dotenv

load_dotenv()

SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME")


def test_google_sheets():
    print("Connect google sheets")

    try:
        gc = gspread.service_account(filename="credentials.json")
        sh = gc.open(SPREADSHEET_NAME)

        worksheet = sh.sheet1
        worksheet.update_acell("A1", "Hello From Python")

        val = worksheet.acell("A1").value

        print(f"✅ Успіх! В таблицю записано і прочитано: '{val}'")
        print("Налаштування Google Cloud пройшло успішно.")

    except Exception as e:
        print(f"❌ Помилка: {e}")
        print(
            "Перевір, чи ти додав email бота (з credentials.json) у доступ до таблиці."
        )

test_google_sheets()
