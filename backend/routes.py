"""API маршруты FastAPI."""

import time

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from config import collection, index_lock, start_time, logger, TOP_K
from html_templates import health_html, health_error_html, format_uptime, dashboard_html

# Ленивый импорт для избежания циклических зависимостей
_ai_provider = None
_scheduler = None


def _get_ai():
    global _ai_provider
    if _ai_provider is None:
        from ai_provider import ai

        _ai_provider = ai
    return _ai_provider


def _get_scheduler():
    global _scheduler
    if _scheduler is None:
        from indexer import scheduler

        _scheduler = scheduler
    return _scheduler


def _get_index_function():
    from indexer import index_documents

    return index_documents


class QueryRequest(BaseModel):
    question: str


# ==================== HEALTH ====================
async def health_handler(request: Request):
    """Возвращает HTML при открытии в браузере, JSON для API."""
    accept = request.headers.get("accept", "")

    try:
        count = collection.count()
        data = {
            "status": "healthy",
            "provider": "yandex",
            "indexed_documents": count,
            "scheduler_running": _get_scheduler().running,
            "uptime_seconds": round(time.time() - start_time, 1),
        }
    except Exception as e:
        if "text/html" in accept:
            return HTMLResponse(content=health_error_html(str(e)), status_code=503)
        raise HTTPException(503, f"Unhealthy: {str(e)}")

    if "text/html" in accept:
        return HTMLResponse(content=health_html(data))

    return data


# ==================== DASHBOARD ====================
def dashboard_handler():
    """Красивая страница дашборда с метриками."""
    return HTMLResponse(content=dashboard_html())


# ==================== READY ====================
def ready_handler():
    return {"status": "ok", "indexed_count": collection.count()}


# ==================== INDEX ====================
def trigger_index():
    if not index_lock.acquire(blocking=False):
        return {"status": "running", "message": "Индексация уже выполняется"}
    try:
        logger.info("🚀 Запуск индексации...")
        index_func = _get_index_function()
        count = index_func()
        return {"status": "success", "indexed_files": count}
    except Exception as e:
        logger.error(f"❌ Ошибка индексации: {e}", exc_info=True)
        raise HTTPException(500, str(e))
    finally:
        index_lock.release()


# ==================== QUERY ====================
def query_handler(req: QueryRequest):
    if not req.question.strip():
        raise HTTPException(400, "Вопрос пустой")
    logger.info(f"❓ Запрос: {req.question}")

    try:
        q_emb = _get_ai().embed([req.question], is_query=True)[0]
        res = collection.query(query_embeddings=[q_emb], n_results=6)
    except Exception as e:
        raise HTTPException(500, f"Ошибка поиска: {str(e)}")

    if not res["documents"][0]:
        return {
            "answer": "Информация не найдена в подключенных документах.",
            "sources": [],
        }

    context = "\n\n".join(
        [
            f"[Источник: {m['source']}]\n{d}"
            for d, m in zip(res["documents"][0], res["metadatas"][0])
        ]
    )
    prompt = f"""Ты технический ассистент. Отвечай ТОЛЬКО на основе приведённых фрагментов.
    Если данных недостаточно, скажи об этом. Не придумывай факты. Всегда указывай источник.

    Вопрос: {req.question}
    Контекст:
    {context}
    Ответ:"""
    try:
        answer = _get_ai().chat(prompt)
        sources = list(set(m["source"] for m in res["metadatas"][0]))
        return {"answer": answer, "sources": sources}
    except Exception as e:
        raise HTTPException(500, f"Ошибка генерации ответа: {str(e)}")
