# QAFlow-AI 🚀

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg?style=for-the-badge&logo=python&logoColor=white)
![Aiogram](https://img.shields.io/badge/Aiogram-3.x-2ca5e0.svg?style=for-the-badge&logo=telegram&logoColor=white)
![Google Gemini](https://img.shields.io/badge/AI-Google%20Gemini-8E75B2.svg?style=for-the-badge&logo=google&logoColor=white)
![Google Sheets](https://img.shields.io/badge/Data-Google%20Sheets-34A853.svg?style=for-the-badge&logo=googlesheets&logoColor=white)

**QAFlow-AI** is an intelligent automation tool designed to bridge the gap between static documentation and active manual testing. It converts User Stories and Acceptance Criteria into actionable test checklists using AI, manages execution via a Telegram Bot, and generates real-time reports in Google Sheets.

---

## 💡 The Problem
Manual QA Engineers often spend valuable time manually parsing requirements (Docx/PDF) into spreadsheets and switching context between testing environments and reporting tools.

## ⚡ The Solution
QAFlow-AI automates the "Setup" phase and streamlines the "Execution" phase:
1.  **Ingest:** Accepts raw `.docx` files with requirements via Telegram.
2.  **Analyze:** Uses **Google Gemini AI** to extract and formulate precise Test Cases.
3.  **Sync:** Automatically populates a Master Checklist in **Google Sheets**.
4.  **Execute:** Sends test cases one-by-one to the tester's Telegram.
5.  **Report:** Updates the sheet in real-time based on "Pass/Fail" interaction.

---

## 🛠 Tech Stack

* **Core:** Python 3.11+
* **Interface:** [aiogram](https://docs.aiogram.dev/) (Asynchronous Telegram Bot Framework)
* **AI Engine:** Google Generative AI (Gemini Pro)
* **Database/Reporting:** Google Sheets API (`gspread`)
* **Document Parsing:** `python-docx`

---

## 🔄 Workflow (MVP)

1.  **User** uploads a requirement document (`.docx`) to the Telegram Bot.
2.  **Bot** parses the text and sends a prompt to **Gemini AI**.
3.  **Gemini** returns a structured list of test cases (e.g., *"Verify error on empty form submission"*).
4.  **Bot** appends these cases to a specific Google Sheet (keeping history of previous runs).
5.  **Bot** starts the "Testing Session":
    * Sends Case #1 to User.
    * User clicks **[✅ Pass]** or **[❌ Failed]**.
    * **Bot** updates the Google Sheet cell color (Green/Red) and status.
    * Repeats until the batch is finished.

---

## 🚀 Roadmap (Future Features)

- [ ] **Smart Bug Reporting:** If a test fails, the bot will ask for details and use AI to generate a Jira-ready bug ticket (Title + Expected Result).
- [ ] **Stats Dashboard:** Daily summary of passed/failed tests.
- [ ] **Multi-user Support:** Allow multiple QAs to test different features simultaneously.

---

## 📦 Installation & Setup

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/your-username/QAFlow-AI.git](https://github.com/your-username/QAFlow-AI.git)
    cd QAFlow-AI
    ```

2.  **Create a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configuration:**
    * Create a `.env` file with your API keys (Telegram Token, Gemini API Key).
    * Place your `google_credentials.json` in the root folder.

---

*Authored by [Evgeniy]*
