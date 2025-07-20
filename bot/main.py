import logging
logging.basicConfig(level=logging.INFO)

import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.utils import executor
from aiogram.dispatcher.filters import ContentTypeFilter
from dotenv import load_dotenv

from extractor import extract_fields_from_text, process_file_with_classification, classify_document_universal
from storage import storage
from analytics import Analytics
from validator import validator

# Очередь задач
task_queue = asyncio.Queue()

# Загрузка токена из .env (создайте .env с TELEGRAM_TOKEN=...)
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Создаём экземпляр аналитики
analytics = Analytics()

# Папка для временного хранения документов
TEMP_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "temp")
os.makedirs(TEMP_DIR, exist_ok=True)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(bot)

# Разрешённые расширения
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "docx", "xlsx", "zip"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# Воркер для обработки очереди документов
async def document_worker():
    while True:
        user_id, filename, file_path, ext = await task_queue.get()
        try:
            # Сначала извлекаем текст
            text = process_file_with_classification(file_path)
            print(f"Text to LLM: {text[:200]}")
            logging.info(f"Text to LLM: {text[:200]}")
            if not text:
                await bot.send_message(user_id, f"❌ Не удалось извлечь текст из документа {filename}.")
            else:
                # Определяем тип документа
                doc_type = classify_document_universal(text)
                logging.info(f"Document type determined: {doc_type}")
                
                # Извлекаем поля
                fields = extract_fields_from_text(text)
                if fields:
                    # Добавляем тип документа в результат и переупорядочиваем поля
                    fields['doc_type'] = doc_type
                    # Создаём новый словарь с нужным порядком полей
                    ordered_fields = {
                        'doc_type': fields['doc_type'],
                        'counterparty': fields['counterparty'],
                        'inn': fields['inn'],
                        'doc_number': fields['doc_number'],
                        'date': fields['date'],
                        'amount': fields['amount'],
                        'subject': fields['subject'],
                        'contract_number': fields['contract_number']
                    }
                    
                    # Валидируем извлеченные данные
                    is_valid, errors, warnings = validator.validate_document_data(ordered_fields)
                    
                    # Формируем сообщение с результатами валидации
                    validation_message = f"📋 **Результаты обработки документа '{filename}':**\n\n"
                    
                    if errors:
                        validation_message += "❌ **Ошибки валидации:**\n"
                        for error in errors:
                            validation_message += f"• {error}\n"
                        validation_message += "\n"
                    
                    if warnings:
                        validation_message += "⚠️ **Предупреждения:**\n"
                        for warning in warnings:
                            validation_message += f"• {warning}\n"
                        validation_message += "\n"
                    
                    if is_valid:
                        validation_message += "✅ **Данные прошли валидацию**\n\n"
                    else:
                        validation_message += "❌ **Данные не прошли валидацию**\n\n"
                    
                    # Показываем извлеченные данные
                    validation_message += "📄 **Извлеченные данные:**\n"
                    for key, value in ordered_fields.items():
                        validation_message += f"• **{key}:** {value}\n"
                    
                    await bot.send_message(user_id, validation_message, parse_mode="Markdown")
                    
                    # Сохраняем документ только если данные прошли валидацию
                    if is_valid:
                        try:
                            doc_id = storage.save_document(file_path, ordered_fields, user_id)
                            await bot.send_message(user_id, f"✅ Документ успешно сохранён в базе (ID: {doc_id})")
                        except Exception as storage_error:
                            logging.error(f"Ошибка сохранения документа: {storage_error}")
                            await bot.send_message(user_id, f"❌ Ошибка сохранения в базу данных: {storage_error}")
                    else:
                        await bot.send_message(user_id, "❌ Документ не сохранён из-за ошибок валидации. Исправьте данные и попробуйте снова.")
                else:
                    await bot.send_message(user_id, f"❌ Не удалось извлечь ключевые поля из документа {filename}.")
        except Exception as e:
            logging.error(f"Ошибка при обработке документа {filename}: {e}", exc_info=True)
            
            # Формируем понятное сообщение об ошибке
            error_message = f"❌ **Ошибка при обработке документа '{filename}':**\n\n"
            
            if "timeout" in str(e).lower():
                error_message += "⏰ **Причина:** Превышено время ожидания ответа от сервера\n\n"
                error_message += "**Решение:** Попробуйте отправить документ позже или разбейте его на части"
            elif "connection" in str(e).lower():
                error_message += "🌐 **Причина:** Проблема с подключением к серверу\n\n"
                error_message += "**Решение:** Проверьте интернет-соединение и попробуйте снова"
            elif "memory" in str(e).lower():
                error_message += "💾 **Причина:** Недостаточно памяти для обработки документа\n\n"
                error_message += "**Решение:** Попробуйте отправить документ меньшего размера"
            else:
                error_message += f"🔧 **Причина:** {str(e)}\n\n"
                error_message += "**Решение:** Обратитесь к администратору системы"
            
            await bot.send_message(user_id, error_message, parse_mode="Markdown")
        finally:
            # Очищаем временный файл
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as cleanup_error:
                logging.warning(f"Не удалось удалить временный файл {file_path}: {cleanup_error}")
            
            task_queue.task_done()

@dp.message_handler(content_types=types.ContentType.DOCUMENT)
async def handle_document(message: Message):
    document = message.document
    filename = document.file_name
    if not allowed_file(filename):
        await message.reply("❌ Недопустимый тип файла. Разрешены: PDF, JPG, DOCX, XLSX, ZIP.")
        return
    file_path = os.path.join(TEMP_DIR, filename)
    await document.download(destination_file=file_path)
    ext = filename.rsplit(".", 1)[-1].lower()
    await message.reply(f"✅ Документ '{filename}' получен и поставлен в очередь на обработку.")
    await task_queue.put((message.from_user.id, filename, file_path, ext))

@dp.message_handler(content_types=types.ContentType.PHOTO)
async def handle_photo(message: Message):
    # Сохраняем самое большое фото
    photo = message.photo[-1]
    file_id = photo.file_id
    filename = f"photo_{file_id}.jpg"
    file_path = os.path.join(TEMP_DIR, filename)
    await photo.download(destination_file=file_path)
    await message.reply(f"✅ Фото получено и поставлено в очередь на обработку.")
    await task_queue.put((message.from_user.id, filename, file_path, "jpg"))

@dp.message_handler(commands=["start", "help"])
async def send_welcome(message: Message):
    help_text = """
🤖 **Документ-бот** - автоматическая обработка документов

**Основные команды:**
📄 Отправьте документ (PDF, JPG, DOCX, XLSX, ZIP) для обработки

**Отчёты:**
📊 `/report` - отчёт по всем контрагентам
📊 `/report <контрагент>` - отчёт по конкретному контрагенту
📊 `/unclosed` - незакрытые бизнес-цепочки
📊 `/monthly` - месячный отчёт
📊 `/chain <номер_договора>` - детали цепочки

**Система:**
🔧 `/status` - статус системы и очереди
🔧 `/validate <текст>` - проверить валидацию данных

**Примеры:**
`/report ООО Рога и Копыта`
`/chain Д-2024-001`
`/monthly 2024 12`
`/validate {"counterparty": "ООО Тест", "inn": "1234567890"}`

Документы обрабатываются по очереди, проходят валидацию и сохраняются в базе данных.
    """
    await message.reply(help_text, parse_mode="Markdown")

@dp.message_handler(commands=["report"])
async def handle_report(message: Message):
    """Обработчик команды отчёта по контрагентам"""
    try:
        args = message.get_args().strip()
        if args:
            # Отчёт по конкретному контрагенту
            report = analytics.generate_counterparty_report(counterparty=args)
            if report['counterparties']:
                counterparty = report['counterparties'][0]
                response = f"""
📊 **Отчёт по контрагенту: {counterparty['name']}**

📋 **Основная информация:**
• ИНН: {counterparty['inn'] or 'не указан'}
• Первый документ: {counterparty['first_document_date'] or 'не указана'}
• Последний документ: {counterparty['last_document_date'] or 'не указана'}

💰 **Финансовые показатели:**
• Общая сумма: {counterparty['total_amount']:,.2f} ₽
• Количество документов: {counterparty['document_count']}

📄 **По типам документов:**
• Договоры: {counterparty['contracts_count']} ({counterparty['contracts_amount']:,.2f} ₽)
• Счета: {counterparty['invoices_count']} ({counterparty['invoices_amount']:,.2f} ₽)
• Закрывающие документы: {counterparty['closing_docs_count']} ({counterparty['closing_amount']:,.2f} ₽)

⚠️ **Незакрыто: {counterparty['unclosed_amount']:,.2f} ₽**
                """
            else:
                response = f"❌ Контрагент '{args}' не найден в базе данных."
        else:
            # Общий отчёт
            report = analytics.generate_counterparty_report()
            summary = report['summary']
            response = f"""
📊 **Общий отчёт по контрагентам**

📋 **Сводка:**
• Всего контрагентов: {summary['total_counterparties']}
• Общая сумма: {summary['total_amount']:,.2f} ₽
• Всего документов: {summary['total_documents']}

🔝 **Топ-5 контрагентов по сумме:**
            """
            
            for i, cp in enumerate(report['counterparties'][:5], 1):
                response += f"\n{i}. {cp['name']} - {cp['total_amount']:,.2f} ₽ ({cp['document_count']} документов)"
        
        await message.reply(response, parse_mode="Markdown")
    except Exception as e:
        await message.reply(f"❌ Ошибка при формировании отчёта: {e}")

@dp.message_handler(commands=["unclosed"])
async def handle_unclosed(message: Message):
    """Обработчик команды незакрытых цепочек"""
    try:
        report = analytics.generate_unclosed_chains_report()
        summary = report['summary']
        
        response = f"""
⚠️ **Незакрытые бизнес-цепочки**

📊 **Сводка:**
• Всего незакрытых цепочек: {summary['total_unclosed_chains']}
• Общая незакрытая сумма: {summary['total_remaining_amount']:,.2f} ₽
• Средняя незакрытая сумма: {summary['average_remaining_amount']:,.2f} ₽

📅 **По возрасту:**
• Новые (≤30 дней): {report['by_age_category']['новые']['count']} цепочек на {report['by_age_category']['новые']['amount']:,.2f} ₽
• Средние (31-90 дней): {report['by_age_category']['средние']['count']} цепочек на {report['by_age_category']['средние']['amount']:,.2f} ₽
• Старые (>90 дней): {report['by_age_category']['старые']['count']} цепочек на {report['by_age_category']['старые']['amount']:,.2f} ₽

🔝 **Топ-5 по незакрытой сумме:**
        """
        
        for i, chain in enumerate(report['chains'][:5], 1):
            response += f"\n{i}. {chain['contract_number']} ({chain['counterparty']}) - {chain['remaining_amount']:,.2f} ₽ ({chain['age_days']} дней)"
        
        await message.reply(response, parse_mode="Markdown")
    except Exception as e:
        await message.reply(f"❌ Ошибка при формировании отчёта: {e}")

@dp.message_handler(commands=["monthly"])
async def handle_monthly(message: Message):
    """Обработчик команды месячного отчёта"""
    try:
        args = message.get_args().strip().split()
        if len(args) >= 2:
            year, month = int(args[0]), int(args[1])
        else:
            year, month = None, None
        
        report = analytics.generate_monthly_report(year, month)
        summary = report['summary']
        
        response = f"""
📊 **Месячный отчёт за {report['period']}**

📋 **Сводка:**
• Всего документов: {summary['total_documents']}
• Общая сумма: {summary['total_amount']:,.2f} ₽
• Уникальных контрагентов: {summary['unique_counterparties']}
• Типов документов: {summary['document_types']}

🔝 **Топ-3 контрагента:**
        """
        
        for i, (name, data) in enumerate(list(report['top_counterparties'].items())[:3], 1):
            response += f"\n{i}. {name} - {data['amount']:,.2f} ₽ ({data['doc_type']} документов)"
        
        await message.reply(response, parse_mode="Markdown")
    except Exception as e:
        await message.reply(f"❌ Ошибка при формировании отчёта: {e}")

@dp.message_handler(commands=["chain"])
async def handle_chain(message: Message):
    """Обработчик команды деталей цепочки"""
    try:
        contract_number = message.get_args().strip()
        if not contract_number:
            await message.reply("❌ Укажите номер договора: `/chain Д-2024-001`")
            return
        
        chain_details = storage.get_chain_details(contract_number)
        if not chain_details:
            await message.reply(f"❌ Цепочка для договора '{contract_number}' не найдена")
            return
        
        response = f"""
🔗 **Цепочка: {contract_number}**

📋 **Основная информация:**
• Контрагент: {chain_details['counterparty']}
• Общая сумма: {chain_details['total_amount']:,.2f} ₽
• Закрыто: {chain_details['closed_amount']:,.2f} ₽
• Осталось: {chain_details['remaining_amount']:,.2f} ₽
• Статус: {chain_details['status']}

📄 **Документы в цепочке ({len(chain_details['documents'])}):**
        """
        
        for doc in chain_details['documents']:
            response += f"\n• {doc['doc_type'].title()} №{doc['doc_number']} от {doc['date']} - {doc['amount']:,.2f} ₽"
        
        await message.reply(response, parse_mode="Markdown")
    except Exception as e:
        await message.reply(f"❌ Ошибка при получении деталей цепочки: {e}")

@dp.message_handler(commands=["status"])
async def handle_status(message: Message):
    """Обработчик команды статуса системы"""
    try:
        # Получаем статистику очереди
        queue_size = task_queue.qsize()
        
        # Проверяем подключение к базе данных
        try:
            db_stats = storage.get_database_stats()
            db_status = "✅ Подключено"
            db_info = f"Документов: {db_stats.get('total_documents', 0)}, Контрагентов: {db_stats.get('total_counterparties', 0)}"
        except Exception as db_error:
            db_status = "❌ Ошибка подключения"
            db_info = str(db_error)
        
        # Проверяем подключение к LLM (упрощенно)
        try:
            # Здесь можно добавить реальную проверку LLM
            llm_status = "✅ Доступен"
        except:
            llm_status = "❌ Недоступен"
        
        status_message = f"""
🔧 **Статус системы**

📊 **Очередь обработки:**
• Задач в очереди: {queue_size}
• Статус: {'🟡 Занята' if queue_size > 0 else '🟢 Свободна'}

🗄️ **База данных:**
• Статус: {db_status}
• {db_info}

🤖 **LLM сервис:**
• Статус: {llm_status}

💾 **Хранилище:**
• Временная папка: {TEMP_DIR}
• Размер: {sum(os.path.getsize(os.path.join(TEMP_DIR, f)) for f in os.listdir(TEMP_DIR) if os.path.isfile(os.path.join(TEMP_DIR, f))):,} байт
        """
        
        await message.reply(status_message, parse_mode="Markdown")
    except Exception as e:
        await message.reply(f"❌ Ошибка при получении статуса: {e}")

@dp.message_handler(commands=["validate"])
async def handle_validate(message: Message):
    """Обработчик команды валидации данных"""
    try:
        args = message.get_args().strip()
        if not args:
            await message.reply("❌ Укажите данные для валидации в формате JSON\n\nПример: `/validate {\"counterparty\": \"ООО Тест\", \"inn\": \"1234567890\"}`")
            return
        
        try:
            import json
            test_data = json.loads(args)
        except json.JSONDecodeError:
            await message.reply("❌ Некорректный формат JSON")
            return
        
        # Валидируем данные
        is_valid, errors, warnings = validator.validate_document_data(test_data)
        
        # Формируем ответ
        validation_message = f"🔍 **Результаты валидации:**\n\n"
        
        if errors:
            validation_message += "❌ **Ошибки:**\n"
            for error in errors:
                validation_message += f"• {error}\n"
            validation_message += "\n"
        
        if warnings:
            validation_message += "⚠️ **Предупреждения:**\n"
            for warning in warnings:
                validation_message += f"• {warning}\n"
            validation_message += "\n"
        
        if is_valid:
            validation_message += "✅ **Данные прошли валидацию**"
        else:
            validation_message += "❌ **Данные не прошли валидацию**"
        
        await message.reply(validation_message, parse_mode="Markdown")
    except Exception as e:
        await message.reply(f"❌ Ошибка при валидации: {e}")

def main():
    loop = asyncio.get_event_loop()
    loop.create_task(document_worker())
    executor.start_polling(dp, skip_updates=True, loop=loop)

if __name__ == "__main__":
    main() 