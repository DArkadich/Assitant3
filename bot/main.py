import logging
import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from dotenv import load_dotenv

from storage import storage
from analytics import Analytics
from validator import validator
from document_processor import processor
from rag import rag_index

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

analytics = Analytics()
TEMP_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "temp")
os.makedirs(TEMP_DIR, exist_ok=True)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "docx", "xlsx", "zip"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

async def notification_callback(user_id: int, message: str):
    try:
        await bot.send_message(user_id, message, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Ошибка отправки уведомления пользователю {user_id}: {e}")

@dp.message()
async def handle_document(message: Message):
    if message.content_type != types.ContentType.DOCUMENT:
        return
    document = message.document
    filename = document.file_name
    if not allowed_file(filename):
        await message.reply("❌ Недопустимый тип файла. Разрешены: PDF, JPG, DOCX, XLSX, ZIP.")
        return
    file_path = os.path.join(TEMP_DIR, filename)
    await document.download(destination_file=file_path)
    task_id = await processor.add_task(message.from_user.id, filename, file_path)
    await message.reply(f"✅ Документ '{filename}' получен и добавлен в очередь обработки (ID: {task_id[:8]})")

@dp.message()
async def handle_photo(message: Message):
    if message.content_type != types.ContentType.PHOTO:
        return
    photo = message.photo[-1]
    file_id = photo.file_id
    filename = f"photo_{file_id}.jpg"
    file_path = os.path.join(TEMP_DIR, filename)
    await photo.download(destination_file=file_path)
    task_id = await processor.add_task(message.from_user.id, filename, file_path)
    await message.reply(f"✅ Фото получено и добавлено в очередь обработки (ID: {task_id[:8]})")

@dp.message(commands=["start", "help"])
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
🔧 `/tasks` - мои задачи обработки
🔧 `/task <id>` - статус конкретной задачи
🔧 `/find <текст>` - семантический поиск по базе

**Примеры:**
`/report ООО Рога и Копыта`
`/chain Д-2024-001`
`/monthly 2024 12`
`/validate {"counterparty": "ООО Тест", "inn": "1234567890"}`

Документы обрабатываются по очереди, проходят валидацию и сохраняются в базе данных.
    """
    await message.reply(help_text, parse_mode="Markdown")

@dp.message(commands=["report"])
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

@dp.message(commands=["unclosed"])
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

@dp.message(commands=["monthly"])
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

@dp.message(commands=["chain"])
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

@dp.message(commands=["status"])
async def handle_status(message: Message):
    """Обработчик команды статуса системы"""
    try:
        # Получаем статистику процессора
        processor_stats = processor.get_stats()
        
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

📊 **Процессор документов:**
• Активных задач: {processor_stats['active_tasks']}
• Задач в очереди: {processor_stats['queue_size']}
• Завершенных задач: {processor_stats['completed_tasks']}
• Воркеров: {processor_stats['workers']}
• Статус: {'🟡 Занята' if processor_stats['queue_size'] > 0 or processor_stats['active_tasks'] > 0 else '🟢 Свободна'}

📈 **Статистика:**
• Всего обработано: {processor_stats['total_processed']}
• Ошибок обработки: {processor_stats['total_failed']}
• Ошибок валидации: {processor_stats['total_validation_failed']}
• Среднее время: {processor_stats['average_processing_time']:.1f} сек

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

@dp.message(commands=["validate"])
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

@dp.message(commands=["tasks"])
async def handle_tasks(message: Message):
    """Обработчик команды списка задач пользователя"""
    try:
        tasks = await processor.get_user_tasks(message.from_user.id)
        
        if not tasks:
            await message.reply("📋 У вас пока нет задач обработки документов.")
            return
        
        response = f"📋 **Ваши задачи обработки ({len(tasks)}):**\n\n"
        
        for i, task in enumerate(tasks[:10], 1):  # Показываем последние 10
            status_emoji = {
                'pending': '⏳',
                'processing': '⚙️',
                'completed': '✅',
                'failed': '❌',
                'validation_failed': '⚠️'
            }.get(task.status.value, '❓')
            
            response += f"{i}. {status_emoji} **{task.filename}** (ID: {task.id[:8]})\n"
            response += f"   Статус: {task.status.value}\n"
            response += f"   Создано: {task.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            
            if task.completed_at:
                response += f"   Завершено: {task.completed_at.strftime('%d.%m.%Y %H:%M')}\n"
            
            if task.error:
                response += f"   Ошибка: {task.error[:50]}...\n"
            
            response += "\n"
        
        if len(tasks) > 10:
            response += f"... и еще {len(tasks) - 10} задач"
        
        await message.reply(response, parse_mode="Markdown")
    except Exception as e:
        await message.reply(f"❌ Ошибка при получении списка задач: {e}")

@dp.message(commands=["task"])
async def handle_task_status(message: Message):
    """Обработчик команды статуса конкретной задачи"""
    try:
        task_id = message.get_args().strip()
        if not task_id:
            await message.reply("❌ Укажите ID задачи: `/task abc12345`")
            return
        
        # Ищем задачу по ID (полному или короткому)
        task = None
        if len(task_id) == 8:
            # Ищем по короткому ID
            for t in list(processor.active_tasks.values()) + list(processor.completed_tasks.values()):
                if t.id.startswith(task_id):
                    task = t
                    break
        else:
            # Ищем по полному ID
            task = await processor.get_task_status(task_id)
        
        if not task:
            await message.reply(f"❌ Задача с ID '{task_id}' не найдена")
            return
        
        # Проверяем, что задача принадлежит пользователю
        if task.user_id != message.from_user.id:
            await message.reply("❌ У вас нет доступа к этой задаче")
            return
        
        status_emoji = {
            'pending': '⏳',
            'processing': '⚙️',
            'completed': '✅',
            'failed': '❌',
            'validation_failed': '⚠️'
        }.get(task.status.value, '❓')
        
        response = f"""
{status_emoji} **Задача: {task.filename}**

🆔 **ID:** {task.id}
📊 **Статус:** {task.status.value}
📅 **Создано:** {task.created_at.strftime('%d.%m.%Y %H:%M:%S')}
        """
        
        if task.started_at:
            response += f"⚙️ **Начато:** {task.started_at.strftime('%d.%m.%Y %H:%M:%S')}\n"
        
        if task.completed_at:
            response += f"✅ **Завершено:** {task.completed_at.strftime('%d.%m.%Y %H:%M:%S')}\n"
            if task.started_at:
                processing_time = (task.completed_at - task.started_at).total_seconds()
                response += f"⏱️ **Время обработки:** {processing_time:.1f} сек\n"
        
        if task.error:
            response += f"\n❌ **Ошибка:** {task.error}\n"
        
        if task.validation_errors:
            response += f"\n⚠️ **Ошибки валидации:**\n"
            for error in task.validation_errors:
                response += f"• {error}\n"
        
        if task.validation_warnings:
            response += f"\n⚠️ **Предупреждения:**\n"
            for warning in task.validation_warnings:
                response += f"• {warning}\n"
        
        if task.result and task.status.value == 'completed':
            response += f"\n📄 **Результат:**\n"
            response += f"• ID в базе: {task.result.get('doc_id')}\n"
            response += f"• Время обработки: {task.result.get('processing_time', 0):.1f} сек\n"
        
        await message.reply(response, parse_mode="Markdown")
    except Exception as e:
        await message.reply(f"❌ Ошибка при получении статуса задачи: {e}")

@dp.message(commands=["find"])
async def handle_find(message: Message):
    query = message.get_args().strip()
    if not query:
        await message.reply("❌ Укажите текст для поиска: `/find <текст или номер>`")
        return
    try:
        results = rag_index.search(query, top_k=5)
        if not results:
            await message.reply("❌ Похожих документов не найдено.")
            return
        response = "🔎 **Похожие документы:**\n\n"
        for i, doc in enumerate(results, 1):
            response += f"{i}. **ID:** {doc['doc_id']}\n"
            response += f"   {doc.get('doc_type', '')} | {doc.get('counterparty', '')} | {doc.get('doc_number', '')}\n"
            response += f"   Сходство: {doc['distance']:.4f}\n"
            response += f"   Фрагмент: {doc['text'][:100]}...\n\n"
        await message.reply(response, parse_mode="Markdown")
    except Exception as e:
        await message.reply(f"❌ Ошибка поиска: {e}")

async def setup_processor():
    """Настройка и запуск процессора документов"""
    # Устанавливаем callback для уведомлений
    processor.set_notification_callback(notification_callback)
    
    # Запускаем процессор
    await processor.start()
    
    logging.info("DocumentProcessor настроен и запущен")

async def main():
    await setup_processor()
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main()) 