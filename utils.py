import os
import gspread
import docx
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import textract

load_dotenv()
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME")


def get_sheet():
    """Підключення до гугл таблиці"""
    try:
        gc = gspread.service_account(filename='credentials.json')
        sh = gc.open(SPREADSHEET_NAME)
        return sh.sheet1
    except Exception as e:
        raise Exception(f"Помилка доступу до Гугл Таблиці: {e}")


def read_docx(file_path):
    """Читає сучасний .docx"""
    doc = docx.Document(file_path)
    full_text = []
    for paragraph in doc.paragraphs:
        if paragraph.text.strip():
            full_text.append(paragraph.text)
    return "\n".join(full_text)


def read_doc(file_path):
    """
    Розумне читання .doc (HTML/MHTML з Confluence або бінарний)
    """
    try:
        # Спроба 1: Читаємо як текст
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Якщо це HTML (Confluence export)
        if "<html" in content or "MIME-Version" in content:
            print("📄 Виявлено HTML/MHTML формат. Чищу від сміття...")
            soup = BeautifulSoup(content, 'html.parser')

            # ВИДАЛЯЄМО СМІТТЯ: скрипти та стилі (CSS)
            for script in soup(["script", "style", "meta", "link", "xml"]):
                script.decompose()

            text = soup.get_text(separator='\n')

            # Прибираємо зайві порожні рядки
            clean_text = "\n".join([line.strip() for line in text.splitlines() if line.strip()])

            print(f"✅ Текст успішно витягнуто. Довжина: {len(clean_text)} символів.")
            return clean_text

        # Спроба 2: Справжній бінарний .doc
        print("⚠️ Спроба читати бінарний .doc через textract...")
        text = textract.process(file_path).decode('utf-8')
        return text

    except Exception as e:
        error_msg = str(e)
        if "antiword" in error_msg or "exit code 127" in error_msg:
            return (
                "ПОМИЛКА ЧИТАННЯ ФАЙЛУ:\n"
                "Це старий бінарний формат .doc, який важко читати на Windows.\n"
                "Будь ласка, перезбережи файл як .docx (Word -> Save As -> .docx) і спробуй знову."
            )
        raise Exception(f"Не вдалося прочитати .doc файл: {e}")


def read_txt(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        with open(file_path, 'r', encoding='cp1251') as f:
            return f.read()


def add_cases_to_sheet(cases_list):
    worksheet = get_sheet()
    existing_rows = len(worksheet.col_values(1))
    start_row = existing_rows + 1
    rows_to_insert = [[case, "PENDING"] for case in cases_list]
    worksheet.append_rows(rows_to_insert)

    result_data = []
    for i, case_text in enumerate(cases_list):
        result_data.append({
            "row": start_row + i,
            "text": case_text
        })
    return result_data


def update_case_status(row_num, status):
    worksheet = get_sheet()
    cell_address = f"B{row_num}"
    worksheet.update_acell(cell_address, status)

    if status == "Pass":
        color = {"red": 0.85, "green": 0.93, "blue": 0.83}
    else:
        color = {"red": 0.96, "green": 0.8, "blue": 0.8}

    worksheet.format(cell_address, {
        "backgroundColor": color,
        "textFormat": {"bold": True}
    })