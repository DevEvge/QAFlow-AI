import os
import asyncio
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv

import ai_helper
import utils

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("Не знайдено BOT_TOKEN у файлі .env")


class TestSession(StatesGroup):
    waiting_for_doc = State()
    testing_process = State()


bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)


def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Почати тестування")]
        ],
        resize_keyboard=True
    )


def get_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Pass", callback_data="status_Pass"),
            InlineKeyboardButton(text="❌ Failed", callback_data="status_Failed")
        ]
    ])


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 Привіт, QA Engineer!\n\n"
        "Я готовий автоматизувати твою роботу.\n"
        "Використовуй кнопки нижче для роботи з ботом.",
        reply_markup=get_main_keyboard()
    )


@router.message(F.text == "📋 Почати тестування")
async def start_testing(message: Message, state: FSMContext):
    await message.answer(
        "📤 **Відмінно!**\n\n"
        "Тепер скинь мені файл з вимогами у форматі:\n"
        "• **.docx** (Word 2007+)\n"
        "• **.doc** (Word 97-2003)\n"
        "• **.txt** (текстовий файл)\n\n"
        "Я перетворю його на чек-лист для тестування."
    )
    await state.set_state(TestSession.waiting_for_doc)


@router.message(TestSession.waiting_for_doc, F.document)
async def handle_document(message: Message, state: FSMContext):
    file_name = message.document.file_name
    if not (file_name.endswith('.docx') or file_name.endswith('.doc') or file_name.endswith('.txt')):
        await message.answer("⚠️ Я розумію тільки файли **.docx**, **.doc** та **.txt**.")
        return

    wait_msg = await message.answer("⏳ Завантажую файл і підключаю AI... Це займе пару секунд.")

    file_id = message.document.file_id
    file = await bot.get_file(file_id)
    file_path = f"temp_{message.document.file_name}"
    await bot.download_file(file.file_path, file_path)

    try:
        if file_name.endswith('.docx'):
            text = utils.read_docx(file_path)
        elif file_name.endswith('.doc'):
            text = utils.read_doc(file_path)
        elif file_name.endswith('.txt'):
            text = utils.read_txt(file_path)
        else:
            await message.answer("⚠️ Непідтримуваний формат файлу.")
            return

        await bot.edit_message_text("🤖 AI аналізує вимоги...", chat_id=message.chat.id, message_id=wait_msg.message_id)
        cases = ai_helper.generate_test_cases(text)

        if not cases:
            await message.answer("❌ AI не зміг виділити кейси. Можливо, файл порожній або текст незрозумілий.")
            return

        await bot.edit_message_text(f"📝 Знайдено {len(cases)} кейсів. Записую в таблицю...", chat_id=message.chat.id,
                                    message_id=wait_msg.message_id)

        session_data = utils.add_cases_to_sheet(cases)

        await state.update_data(queue=session_data, current_index=0)
        await state.set_state(TestSession.testing_process)

        await message.answer("✅ **Готово! Починаємо тестування.**")

        if os.path.exists(file_path):
            os.remove(file_path)

        await send_next_case(message, state)

    except Exception as e:
        await message.answer(f"❌ Критична помилка: {e}")
        if os.path.exists(file_path):
            os.remove(file_path)


async def send_next_case(message: Message, state: FSMContext):
    data = await state.get_data()
    queue = data.get('queue', [])
    index = data.get('current_index', 0)

    if index >= len(queue):
        await message.answer(
            "🎉 **Тестування завершено!** Всі кейси з цього файлу пройдені.\n\n"
            "Використовуй кнопку нижче, щоб почати нову сесію тестування.",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        return

    case = queue[index]

    text = (
        f"🛠 **Кейс {index + 1} з {len(queue)}**\n"
        f"➖➖➖➖➖➖➖➖\n"
        f"🔸 {case['text']}\n"
    )

    await message.answer(text, reply_markup=get_keyboard())


@router.callback_query(TestSession.testing_process, F.data.startswith("status_"))
async def process_callback(callback: CallbackQuery, state: FSMContext):
    status = callback.data.split("_")[1]

    data = await state.get_data()
    index = data.get('current_index')
    queue = data.get('queue')

    current_case = queue[index]
    row_number = current_case['row']

    try:
        utils.update_case_status(row_number, status)
    except Exception as e:
        await callback.answer(f"Помилка запису: {e}", show_alert=True)
        return

    icon = "✅" if status == "Pass" else "🔴"
    await callback.message.edit_text(
        f"~~{current_case['text']}~~\n\n**Результат:** {icon} {status}",
        reply_markup=None
    )

    await state.update_data(current_index=index + 1)
    await send_next_case(callback.message, state)


@router.message(F.text)
async def handle_random_text(message: Message, state: FSMContext):
    await message.answer(
        "Використовуй кнопки нижче для роботи з ботом.",
        reply_markup=get_main_keyboard()
    )


async def main():
    print("🚀 Бот запущений і чекає повідомлень...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())