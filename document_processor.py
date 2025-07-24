import asyncio
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import json

from extractor import extract_fields_from_text, process_file_with_classification, classify_document_universal
from storage import storage
from validator import validator
from rag import get_rag_index

class ProcessingStatus(Enum):
    """Статусы обработки документа"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    VALIDATION_FAILED = "validation_failed"

@dataclass
class ProcessingTask:
    """Задача обработки документа"""
    id: str
    user_id: int
    filename: str
    file_path: str
    status: ProcessingStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict] = None
    error: Optional[str] = None
    validation_errors: List[str] = None
    validation_warnings: List[str] = None

class DocumentProcessor:
    """Асинхронный процессор документов"""
    
    def __init__(self, max_workers: int = 3):
        self.max_workers = max_workers
        self.task_queue = asyncio.Queue()
        self.active_tasks: Dict[str, ProcessingTask] = {}
        self.completed_tasks: Dict[str, ProcessingTask] = {}
        self.workers: List[asyncio.Task] = []
        self.notification_callback: Optional[Callable] = None
        self.is_running = False
        
        # Статистика
        self.stats = {
            'total_processed': 0,
            'total_failed': 0,
            'total_validation_failed': 0,
            'average_processing_time': 0.0
        }
    
    def set_notification_callback(self, callback: Callable):
        """Устанавливает callback для уведомлений"""
        self.notification_callback = callback
    
    async def start(self):
        """Запускает процессор"""
        if self.is_running:
            return
        
        self.is_running = True
        logging.info(f"Запуск DocumentProcessor с {self.max_workers} воркерами")
        
        # Запускаем воркеры
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self.workers.append(worker)
        
        logging.info("DocumentProcessor запущен")
    
    async def stop(self):
        """Останавливает процессор"""
        if not self.is_running:
            return
        
        self.is_running = False
        logging.info("Остановка DocumentProcessor...")
        
        # Останавливаем воркеры
        for worker in self.workers:
            worker.cancel()
        
        # Ждем завершения всех воркеров
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()
        
        logging.info("DocumentProcessor остановлен")
    
    async def add_task(self, user_id: int, filename: str, file_path: str) -> str:
        """Добавляет задачу в очередь"""
        task_id = str(uuid.uuid4())
        task = ProcessingTask(
            id=task_id,
            user_id=user_id,
            filename=filename,
            file_path=file_path,
            status=ProcessingStatus.PENDING,
            created_at=datetime.now()
        )
        
        self.active_tasks[task_id] = task
        await self.task_queue.put(task)
        
        logging.info(f"Добавлена задача {task_id} для пользователя {user_id}: {filename}")
        
        # Уведомляем о добавлении в очередь
        if self.notification_callback:
            await self.notification_callback(
                user_id, 
                f"📋 Документ '{filename}' добавлен в очередь обработки (ID: {task_id[:8]})"
            )
        
        return task_id
    
    async def get_task_status(self, task_id: str) -> Optional[ProcessingTask]:
        """Получает статус задачи"""
        if task_id in self.active_tasks:
            return self.active_tasks[task_id]
        elif task_id in self.completed_tasks:
            return self.completed_tasks[task_id]
        return None
    
    async def get_user_tasks(self, user_id: int) -> List[ProcessingTask]:
        """Получает все задачи пользователя"""
        tasks = []
        
        # Активные задачи
        for task in self.active_tasks.values():
            if task.user_id == user_id:
                tasks.append(task)
        
        # Завершенные задачи (последние 10)
        user_completed = [t for t in self.completed_tasks.values() if t.user_id == user_id]
        tasks.extend(sorted(user_completed, key=lambda x: x.completed_at, reverse=True)[:10])
        
        return tasks
    
    async def _worker(self, worker_name: str):
        """Воркер для обработки задач"""
        logging.info(f"Воркер {worker_name} запущен")
        
        while self.is_running:
            try:
                # Получаем задачу из очереди
                task = await asyncio.wait_for(self.task_queue.get(), timeout=1.0)
                
                # Обрабатываем задачу
                await self._process_task(task, worker_name)
                
                # Отмечаем задачу как выполненную
                self.task_queue.task_done()
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logging.error(f"Ошибка в воркере {worker_name}: {e}")
        
        logging.info(f"Воркер {worker_name} остановлен")
    
    async def _process_task(self, task: ProcessingTask, worker_name: str):
        """Обрабатывает одну задачу"""
        start_time = datetime.now()
        task.started_at = start_time
        task.status = ProcessingStatus.PROCESSING
        
        logging.info(f"Воркер {worker_name} обрабатывает задачу {task.id}: {task.filename}")
        
        # Уведомляем о начале обработки
        if self.notification_callback:
            await self.notification_callback(
                task.user_id,
                f"⚙️ Начата обработка документа '{task.filename}' (ID: {task.id[:8]})"
            )
        
        try:
            # Извлекаем текст из документа
            text = process_file_with_classification(task.file_path)
            if not text:
                raise Exception("Не удалось извлечь текст из документа")

            # Явно определяем тип документа
            doc_type = classify_document_universal(text)
            if self.notification_callback:
                await self.notification_callback(task.user_id, f"Определён тип документа: <b>{doc_type}</b>")

            # Извлекаем поля, передаём doc_type для контекстного поиска даты и других полей
            rag_results = get_rag_index().search(text, top_k=3)
            rag_context = [doc['text'] for doc in rag_results]
            fields = extract_fields_from_text(text, rag_context=rag_context, doc_type=doc_type) if 'doc_type' in extract_fields_from_text.__code__.co_varnames else extract_fields_from_text(text, rag_context=rag_context)

            if not fields:
                raise Exception("Не удалось извлечь ключевые поля из документа")

            # Добавляем тип документа и упорядочиваем поля
            fields['doc_type'] = doc_type
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

            # Валидируем данные с учётом типа документа
            is_valid, errors, warnings = validator.validate_document_data(ordered_fields, doc_type=doc_type)
            task.validation_errors = errors
            task.validation_warnings = warnings
            
            if not is_valid:
                task.status = ProcessingStatus.VALIDATION_FAILED
                task.error = f"Ошибки валидации: {', '.join(errors)}"
                task.result = ordered_fields
                
                # Уведомляем об ошибках валидации
                if self.notification_callback:
                    validation_message = f"❌ **Ошибки валидации документа '{task.filename}':**\n\n"
                    for error in errors:
                        validation_message += f"• {error}\n"
                    if warnings:
                        validation_message += "\n⚠️ **Предупреждения:**\n"
                        for warning in warnings:
                            validation_message += f"• {warning}\n"
                    
                    await self.notification_callback(task.user_id, validation_message)
                
                self.stats['total_validation_failed'] += 1
                return
            
            # Сохраняем документ в базу данных
            doc_id = storage.save_document(task.file_path, ordered_fields, task.user_id)
            
            # Индексируем документ
            try:
                doc_text = " ".join(str(v) for v in ordered_fields.values() if v)
                get_rag_index().add_document(str(doc_id), doc_text, meta=ordered_fields)
            except Exception as e:
                logging.warning(f"RAG indexing failed: {e}")
            
            # Завершаем задачу
            task.status = ProcessingStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = {
                'doc_id': doc_id,
                'fields': ordered_fields,
                'processing_time': (task.completed_at - start_time).total_seconds()
            }
            
            # Уведомляем об успешном завершении
            if self.notification_callback:
                success_message = f"""
✅ **Документ '{task.filename}' успешно обработан!**

📄 **Извлеченные данные:**
• Тип: {ordered_fields['doc_type']}
• Контрагент: {ordered_fields['counterparty']}
• Номер: {ordered_fields['doc_number']}
• Сумма: {ordered_fields['amount']}
• Дата: {ordered_fields['date']}

🆔 **ID в базе:** {doc_id}
⏱️ **Время обработки:** {(task.completed_at - start_time).total_seconds():.1f} сек
                """
                
                if warnings:
                    success_message += "\n⚠️ **Предупреждения:**\n"
                    for warning in warnings:
                        success_message += f"• {warning}\n"
                
                await self.notification_callback(task.user_id, success_message)
            
            self.stats['total_processed'] += 1
            
        except Exception as e:
            # Обрабатываем ошибку
            task.status = ProcessingStatus.FAILED
            task.completed_at = datetime.now()
            task.error = str(e)
            
            logging.error(f"Ошибка обработки задачи {task.id}: {e}")
            
            # Уведомляем об ошибке
            if self.notification_callback:
                error_message = f"""
❌ **Ошибка обработки документа '{task.filename}':**

🔧 **Причина:** {str(e)}

💡 **Возможные решения:**
• Проверьте качество изображения/PDF
• Убедитесь, что документ читаемый
• Попробуйте отправить документ позже
                """
                
                await self.notification_callback(task.user_id, error_message)
            
            self.stats['total_failed'] += 1
        
        finally:
            # Перемещаем задачу в завершенные
            self.completed_tasks[task.id] = task
            if task.id in self.active_tasks:
                del self.active_tasks[task.id]
            
            # Очищаем временный файл
            try:
                if os.path.exists(task.file_path):
                    os.remove(task.file_path)
            except Exception as cleanup_error:
                logging.warning(f"Не удалось удалить временный файл {task.file_path}: {cleanup_error}")
            
            # Обновляем статистику
            if task.status == ProcessingStatus.COMPLETED:
                processing_time = (task.completed_at - start_time).total_seconds()
                total_processed = self.stats['total_processed']
                current_avg = float(self.stats['average_processing_time'])
                self.stats['average_processing_time'] = (current_avg * (total_processed - 1) + processing_time) / total_processed
    
    def get_stats(self) -> Dict:
        """Получает статистику процессора"""
        return {
            **self.stats,
            'active_tasks': len(self.active_tasks),
            'completed_tasks': len(self.completed_tasks),
            'queue_size': self.task_queue.qsize(),
            'workers': len(self.workers)
        }

# Глобальный экземпляр процессора
processor = DocumentProcessor() 