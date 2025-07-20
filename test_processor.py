#!/usr/bin/env python3
"""
Тест асинхронного процессора документов
"""

import asyncio
import logging
from document_processor_standalone import DocumentProcessor, ProcessingStatus

# Настройка логирования
logging.basicConfig(level=logging.INFO)

async def test_processor():
    """Тестирует процессор документов"""
    print("🧪 Тестирование DocumentProcessor...")
    
    # Создаем процессор
    processor = DocumentProcessor(max_workers=2)
    
    # Простой callback для уведомлений
    async def test_callback(user_id: int, message: str):
        print(f"📨 Уведомление для {user_id}: {message}")
    
    # Устанавливаем callback
    processor.set_notification_callback(test_callback)
    
    # Запускаем процессор
    await processor.start()
    
    print("✅ Процессор запущен")
    
    # Проверяем статистику
    stats = processor.get_stats()
    print(f"📊 Статистика: {stats}")
    
    # Симулируем добавление задач (без реальных файлов)
    print("\n📋 Симуляция добавления задач...")
    
    # Создаем тестовые задачи
    test_tasks = [
        (123, "test_doc1.pdf", "/tmp/test1.pdf"),
        (456, "test_doc2.jpg", "/tmp/test2.jpg"),
        (789, "test_doc3.docx", "/tmp/test3.docx"),
    ]
    
    task_ids = []
    for user_id, filename, file_path in test_tasks:
        try:
            task_id = await processor.add_task(user_id, filename, file_path)
            task_ids.append(task_id)
            print(f"✅ Добавлена задача {task_id[:8]} для {filename}")
        except Exception as e:
            print(f"❌ Ошибка добавления задачи: {e}")
    
    # Ждем немного для обработки
    print("\n⏳ Ожидание обработки...")
    await asyncio.sleep(5)
    
    # Проверяем статусы задач
    print("\n📊 Проверка статусов задач:")
    for task_id in task_ids:
        task = await processor.get_task_status(task_id)
        if task:
            print(f"Задача {task_id[:8]}: {task.status.value}")
        else:
            print(f"Задача {task_id[:8]}: не найдена")
    
    # Проверяем статистику
    stats = processor.get_stats()
    print(f"\n📈 Обновленная статистика: {stats}")
    
    # Останавливаем процессор
    print("\n🛑 Остановка процессора...")
    await processor.stop()
    
    print("✅ Тест завершен")

if __name__ == "__main__":
    asyncio.run(test_processor()) 