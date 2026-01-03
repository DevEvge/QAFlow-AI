import os
import asyncio
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, \
    InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv

import ai_helper
import utils

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN: raise ValueError("Не знайдено BOT_TOKEN")


class TestSession(StatesGroup):
    main_menu = State()
    choosing_action = State()
    waiting_for_doc = State()
    selecting_module = State()
    testing = State()
    waiting_for_bug_desc = State()


bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)


# --- UI ELEMENTS (KEYBOARDS) ---

def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🚀 Розпочати сесію тестування")]],
        resize_keyboard=True
    )


def get_back_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🔙 Повернутися в меню")]],
        resize_keyboard=True
    )


def get_action_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 Завантажити нові вимоги", callback_data="action_upload")],
        [InlineKeyboardButton(text="▶️ Продовжити тестування", callback_data="action_continue")]
    ])


def get_modules_keyboard(modules_dict):
    builder = []
    for name, row in modules_dict.items():
        # Кнопка виглядає як "📦 Auth Module", але передає "mod_15"
        builder.append([InlineKeyboardButton(text=f"📦 {name}", callback_data=f"mod_{row}")])

    builder.append([InlineKeyboardButton(text="➕ Додати інший файл", callback_data="action_upload")])
    return InlineKeyboardMarkup(inline_keyboard=builder)


def get_test_keyboard(row_number):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Pass", callback_data=f"pass_{row_number}"),
            InlineKeyboardButton(text="❌ Failed", callback_data=f"fail_{row_number}")
        ]
    ])


# --- HANDLERS ---

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 **Вітаю в QAFlow AI!**\n\n"
        "Я ваш інтелектуальний асистент для автоматизації ручного тестування.\n"
        "Я допоможу перетворити документацію на структуровані чек-листи та згенерувати баг-репорти.\n\n"
        "Натисніть кнопку нижче, щоб почати.",
        reply_markup=get_main_keyboard()
    )


@router.message(F.text == "🔙 Повернутися в меню")
async def go_back(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🏠 Ви повернулися до головного меню.", reply_markup=get_main_keyboard())


@router.message(F.text == "🚀 Розпочати сесію тестування")
async def start_flow(message: Message, state: FSMContext):
    status_msg = await message.answer("⏳ Перевірка статусу завдань...", reply_markup=get_back_keyboard())

    pending_modules_dict = utils.get_unique_pending_modules()

    await status_msg.delete()

    if pending_modules_dict:
        await message.answer(
            f"🔎 **Знайдено активні завдання.**\n"
            f"Кількість модулів у роботі: {len(pending_modules_dict)}.\n\n"
            "Бажаєте продовжити або завантажити нові вимоги?",
            reply_markup=get_action_keyboard()
        )
        await state.set_state(TestSession.choosing_action)
    else:
        await message.answer(
            "✅ **Всі заплановані тести виконано.**\n\n"
            "Будь ласка, завантажте файл з вимогами (.docx, .doc, .txt), щоб створити новий набір тестів.",
            reply_markup=get_back_keyboard()
        )
        await state.set_state(TestSession.waiting_for_doc)


@router.callback_query(TestSession.choosing_action, F.data == "action_upload")
async def action_upload(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📤 **Завантажте документ з вимогами.**\nПідтримуються формати: .docx, .doc, .txt")
    await state.set_state(TestSession.waiting_for_doc)


@router.callback_query(TestSession.choosing_action, F.data == "action_continue")
async def action_continue(callback: CallbackQuery, state: FSMContext):
    modules_dict = utils.get_unique_pending_modules()
    await callback.message.edit_text("📂 **Оберіть модуль для тестування:**",
                                     reply_markup=get_modules_keyboard(modules_dict))
    await state.set_state(TestSession.selecting_module)


@router.message(TestSession.waiting_for_doc, F.document)
async def handle_document(message: Message, state: FSMContext):
    status_msg = await message.answer("⏳ **Ініціалізація обробки файлу...**")

    file_id = message.document.file_id
    file_name = message.document.file_name
    file = await bot.get_file(file_id)
    file_path = f"temp_{file_name}"
    await bot.download_file(file.file_path, file_path)

    try:
        await status_msg.edit_text("📖 **Зчитування вмісту документу...**")

        if file_path.endswith('.docx'):
            text = utils.read_docx(file_path)
        elif file_path.endswith('.doc'):
            text = utils.read_doc(file_path)
        else:
            text = utils.read_txt(file_path)

        await status_msg.edit_text("🧠 **AI аналізує бізнес-логіку та формує сценарії...**")

        module_name, cases = ai_helper.generate_test_cases(text)

        if module_name is None:
            await status_msg.edit_text("❌ Помилка сервісу AI. Спробуйте пізніше або перевірте файл.")
            return

        if not cases:
            await status_msg.edit_text("⚠️ Не вдалося виділити тест-кейси. Перевірте, чи містить файл чіткі вимоги.")
            return

        await status_msg.edit_text(
            f"📝 **Синхронізація з таблицею:**\n📦 Модуль: {module_name}\n🔢 Кількість кейсів: {len(cases)}")

        utils.add_cases_to_sheet(cases, module_name)

        modules_dict = utils.get_unique_pending_modules()
        await status_msg.edit_text(
            f"✅ **Успішно!** Модуль '{module_name}' додано до черги.\n\nОберіть модуль для початку роботи:",
            reply_markup=get_modules_keyboard(modules_dict)
        )
        await state.set_state(TestSession.selecting_module)

    except Exception as e:
        await status_msg.edit_text(f"❌ Системна помилка: {e}")
    finally:
        if os.path.exists(file_path): os.remove(file_path)


@router.message(TestSession.waiting_for_doc, F.text)
async def handle_text_instead(message: Message, state: FSMContext):
    if message.text == "🔙 Повернутися в меню":
        await go_back(message, state)
        return
    await message.answer("⚠️ Очікується файл документу, а не текст.\nНатисніть '🔙 Повернутися в меню' для скасування.")


@router.callback_query(TestSession.selecting_module, F.data == "action_upload")
async def upload_more(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📤 **Завантажте наступний файл.**")
    await state.set_state(TestSession.waiting_for_doc)


@router.callback_query(TestSession.selecting_module, F.data.startswith("mod_"))
async def select_module(callback: CallbackQuery, state: FSMContext):
    row_num = int(callback.data.split("_")[1])
    module_name = utils.get_module_name_by_row(row_num)

    if not module_name:
        await callback.answer("❌ Модуль не знайдено (актуалізуйте таблицю).", show_alert=True)
        return

    await state.update_data(current_module=module_name)
    await callback.message.edit_text(f"🚀 **Запуск модуля:** {module_name}")
    await state.set_state(TestSession.testing)
    await send_next_case(callback.message, module_name)


async def send_next_case(message: Message, module_name):
    case_data = utils.get_next_pending_case_by_module(module_name)
    if case_data:
        text = (
            f"📦 **{module_name}**\n"
            f"🆔 **Case #{case_data['row']}**\n"
            f"➖➖➖➖➖➖➖➖\n"
            f"🔸 {case_data['text']}"
        )
        await message.answer(text, reply_markup=get_test_keyboard(case_data['row']))
    else:
        await message.answer(f"🎉 **Модуль '{module_name}' успішно протестовано!**", reply_markup=get_main_keyboard())
        await state.clear()


@router.callback_query(F.data.startswith("pass_"))
async def process_pass(callback: CallbackQuery, state: FSMContext):
    row_number = int(callback.data.split("_")[1])
    try:
        text_lines = callback.message.text.split('\n')
        case_text = text_lines[-1]
        utils.update_case_status(row_number, "Pass")
        await callback.message.edit_text(f"~~{case_text}~~\n\n✅ **Passed**", reply_markup=None)
    except Exception as e:
        print(f"❌ Error inside process_pass: {e}")
        await callback.message.edit_reply_markup(reply_markup=None)

    data = await state.get_data()
    module_name = data.get('current_module')
    if module_name: await send_next_case(callback.message, module_name)


@router.callback_query(F.data.startswith("fail_"))
async def process_fail(callback: CallbackQuery, state: FSMContext):
    row_number = int(callback.data.split("_")[1])
    text_lines = callback.message.text.split('\n')
    case_text = text_lines[-1].replace("🔸 ", "")

    await state.update_data(failed_row=row_number, failed_case_text=case_text, msg_id=callback.message.message_id)
    await callback.message.answer(
        "✍️ **Реєстрація дефекту**\n\n"
        "Опишіть фактичний результат (Actual Result) або деталі помилки.\n"
        "AI використає це для створення Bug Report.",
        reply_markup=ReplyKeyboardMarkup(keyboard=[], resize_keyboard=True)
    )
    await state.set_state(TestSession.waiting_for_bug_desc)
    await callback.answer()


@router.message(TestSession.waiting_for_bug_desc)
async def process_bug_desc(message: Message, state: FSMContext):
    user_desc = message.text
    data = await state.get_data()

    status_msg = await message.answer("⏳ **Генерація Bug Report (English)...**")
    bug_report = ai_helper.generate_bug_report(data['failed_case_text'], user_desc)

    await status_msg.edit_text("📝 **Збереження звіту в базу даних...**")
    utils.update_case_status(data['failed_row'], "Failed", bug_report)
    await status_msg.edit_text(f"🐛 **Bug Report Created:**\n{bug_report}")

    try:
        await bot.edit_message_text(f"~~{data['failed_case_text']}~~\n\n❌ **Failed**", chat_id=message.chat.id,
                                    message_id=data['msg_id'], reply_markup=None)
    except Exception as e:
        print(f"❌ Error processing bug report msg update: {e}")

    module_name = data.get('current_module')
    await state.set_state(TestSession.testing)
    if module_name: await send_next_case(message, module_name)


@router.message()
async def global_reset(message: Message, state: FSMContext):
    if await state.get_state() == TestSession.waiting_for_bug_desc: return
    await state.clear()
    await message.answer("🏠 Скидання контексту. Головне меню.", reply_markup=get_main_keyboard())


async def main():
    print("🚀 QAFlow AI Bot is running...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())