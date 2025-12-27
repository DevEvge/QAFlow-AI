import os
import gspread
import docx
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import textract

load_dotenv()
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME")


def get_sheet():
    try:
        gc = gspread.service_account(filename='credentials.json')
        sh = gc.open(SPREADSHEET_NAME)
        return sh.sheet1
    except Exception as e:
        raise Exception(f"Помилка доступу до Гугл Таблиці: {e}")


def read_docx(file_path):
    doc = docx.Document(file_path)
    full_text = []
    for paragraph in doc.paragraphs:
        if paragraph.text.strip():
            full_text.append(paragraph.text)
    return "\n".join(full_text)


def read_doc(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        if "<html" in content or "MIME-Version" in content:
            soup = BeautifulSoup(content, 'html.parser')
            for script in soup(["script", "style", "meta", "link", "xml"]):
                script.decompose()
            text = soup.get_text(separator='\n')
            return "\n".join([line.strip() for line in text.splitlines() if line.strip()])

        text = textract.process(file_path).decode('utf-8')
        return text
    except Exception as e:
        if "antiword" in str(e): return "Помилка: Старий .doc формат. Збережіть як .docx"
        raise e


def read_txt(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except:
        with open(file_path, 'r', encoding='cp1251') as f:
            return f.read()


def add_cases_to_sheet(cases_list):
    worksheet = get_sheet()
    rows = [[case, "PENDING", ""] for case in cases_list]  # Додаємо пусту колонку для багів
    worksheet.append_rows(rows)


def get_next_pending_case():
    worksheet = get_sheet()
    statuses = worksheet.col_values(2)
    try:
        pending_index = statuses.index("PENDING")
        row_num = pending_index + 1
        case_text = worksheet.acell(f"A{row_num}").value
        return {"row": row_num, "text": case_text}
    except ValueError:
        return None


def update_case_status(row_num, status, bug_report=None):
    """
    Оновлює статус і (опціонально) записує баг-репорт у колонку C.
    """
    worksheet = get_sheet()

    # 1. Оновлюємо статус (Колонка B)
    worksheet.update_acell(f"B{row_num}", status)

    # 2. Якщо є баг-репорт - пишемо в Колонку C
    if bug_report:
        worksheet.update_acell(f"C{row_num}", bug_report)

    # 3. Фарбуємо
    if status == "Pass":
        color = {"red": 0.85, "green": 0.93, "blue": 0.83}
    else:
        color = {"red": 0.96, "green": 0.8, "blue": 0.8}

    worksheet.format(f"B{row_num}", {
        "backgroundColor": color,
        "textFormat": {"bold": True}
    })