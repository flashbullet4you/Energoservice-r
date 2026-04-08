"""Индексация документов в ChromaDB."""

import os
import threading
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from config import (
    DOC_DIR,
    DWG_CACHE_DIR,
    INDEX_INTERVAL,
    collection,
    index_lock,
    logger,
)
from document_processor import convert_dwgs, extract_text, chunk_text


# Ленивый импорт для избежания циклических зависимостей
_ai_provider = None


def _get_ai():
    global _ai_provider
    if _ai_provider is None:
        from ai_provider import ai

        _ai_provider = ai
    return _ai_provider


# ==================== ИНДЕКСАЦИЯ ====================
def index_documents():
    convert_dwgs()  # <- Сначала конвертируем DWG
    logger.info("🔍 Сканирование документов...")

    # Индексируем основную папку и кэш DWG
    scan_dirs = [DOC_DIR, DWG_CACHE_DIR]
    added = 0

    # Получаем уже проиндексированные файлы из метаданных
    existing = set()
    if collection.count() > 0:
        data = collection.get()
        for meta in data.get("metadatas", []):
            if meta and "source" in meta:
                existing.add(f"{meta['source']}_{meta.get('mtime', 0)}")

    for scan_dir in scan_dirs:
        if not os.path.exists(scan_dir):
            continue
        for root, _, files in os.walk(scan_dir):
            for f in files:
                if f.startswith("~$"):
                    continue
                path = os.path.join(root, f)
                ext = Path(path).suffix.lower()
                if ext not in (".pdf", ".docx", ".xlsx"):
                    continue

                meta_key = f"{path}_{os.path.getmtime(path)}"
                if meta_key in existing:
                    continue

                logger.debug(f"📄 Обработка: {path}")
                text = extract_text(path)
                chunks = chunk_text(text, path)
                if not chunks:
                    continue

                ids = [c["id"] for c in chunks]
                docs = [c["text"] for c in chunks]
                metas = [
                    {"source": c["source"], "mtime": os.path.getmtime(path)}
                    for c in chunks
                ]

                for i in range(0, len(docs), 50):
                    collection.add(
                        ids=ids[i : i + 50],
                        embeddings=_get_ai().embed(docs[i : i + 50]),
                        documents=docs[i : i + 50],
                        metadatas=metas[i : i + 50],
                    )
                added += 1
    logger.info(f"✅ Индексация завершена. Добавлено файлов: {added}")
    return added


# ==================== ФОНОВАЯ ИНДЕКСАЦИЯ ====================
scheduler = BackgroundScheduler()


def run_index_job():
    if not index_lock.acquire(blocking=False):
        logger.info("⏳ Плановая индексация пропущена: уже выполняется другая задача.")
        return
    try:
        index_documents()
    except Exception as e:
        logger.error(f"❌ Ошибка фоновой индексации: {e}", exc_info=True)
    finally:
        index_lock.release()


def setup_scheduler():
    """Настройка планировщика фоновой индексации."""
    scheduler.add_job(
        run_index_job,
        IntervalTrigger(minutes=INDEX_INTERVAL),
        id="index_job",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler
