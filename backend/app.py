# import base64
import hashlib
import logging
import logging.handlers
import os
import subprocess
import threading
import time
import urllib3

# import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List

import chromadb
import openpyxl
import pypdf
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from docx import Document
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==================== ЛОГИРОВАНИЕ ====================
os.makedirs("logs", exist_ok=True)
log_handler = logging.handlers.RotatingFileHandler(
    "logs/app.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
)
log_handler.setFormatter(
    logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)-10s | %(message)s")
)
logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(), log_handler])
logger = logging.getLogger("doc_search")

load_dotenv()
start_time = time.time()

# ==================== КОНФИГ ====================
DOC_DIR = os.getenv("DOC_DIR", "./docs")
DWG_CACHE_DIR = os.getenv("DWG_CACHE_DIR", "./dwg_cache")
DWG_CONVERTER_CMD = os.getenv("DWG_CONVERTER_CMD", "ODAFileConverter")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))
TOP_K = int(os.getenv("TOP_K", "6"))
INDEX_INTERVAL = int(os.getenv("INDEX_INTERVAL_MINUTES", "30"))
SSL_VERIFY = os.getenv("SSL_VERIFY", "false").lower() == "true"

chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(name="tech_docs")
index_lock = threading.Lock()


# ==================== КОНВЕРТАЦИЯ DWG ====================
def convert_dwgs():
    """Пакетная конвертация всех DWG в директории -> PDF."""
    os.makedirs(DWG_CACHE_DIR, exist_ok=True)
    dwg_files = list(Path(DOC_DIR).rglob("*.dwg"))
    if not dwg_files:
        return

    logger.info(f"📐 Найдено {len(dwg_files)} DWG файлов. Запуск конвертации...")
    cmd = [
        DWG_CONVERTER_CMD,
        "-i",
        DOC_DIR,
        "-o",
        DWG_CACHE_DIR,
        "-v",
        "ACAD2018",
        "-f",
        "PDF",
        "-r",
        "-x",
        "-l",
    ]
    try:
        subprocess.run(cmd, check=True, timeout=600, capture_output=True)
        logger.info("✅ DWG -> PDF конвертация завершена.")
    except subprocess.CalledProcessError as e:
        logger.warning(f"⚠️ Ошибка конвертера: {e.stderr.decode()[:200]}")
    except FileNotFoundError:
        logger.warning(
            f"⚠️ Конвертер '{DWG_CONVERTER_CMD}' не найден в PATH. DWG будут пропущены."
        )
    except Exception as e:
        logger.warning(f"⚠️ Конвертация DWG пропущена: {e}")


# ==================== YANDEX AI PROVIDER ====================
class YandexAIProvider:
    def __init__(self):
        self.api_key = os.getenv("YANDEX_API_KEY")
        self.folder_id = os.getenv("YANDEX_FOLDER_ID", "")
        self.embed_model_doc = f"emb://{self.folder_id}/text-search-doc/latest"
        self.embed_model_query = f"emb://{self.folder_id}/text-search-query/latest"
        self.chat_model = f"gpt://{self.folder_id}/yandexgpt/latest"

    def _headers(self):
        return {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json",
        }

    def embed(self, texts: List[str], is_query: bool = False) -> List[List[float]]:
        """Генерация эмбеддингов для текстов.

        is_query: True для коротких запросов, False для длинных документов
        """
        headers = self._headers()
        model_uri = self.embed_model_query if is_query else self.embed_model_doc
        url = "https://llm.api.cloud.yandex.net/foundationModels/v1/textEmbedding"

        all_embeddings = []
        for text in texts:
            payload = {
                "modelUri": model_uri,
                "text": text,
            }
            r = requests.post(
                url,
                headers=headers,
                json=payload,
                verify=SSL_VERIFY,
            )

            if r.status_code != 200:
                logger.error(f"Yandex API error {r.status_code}: {r.text}")
                r.raise_for_status()

            response = r.json()

            if "embedding" in response:
                all_embeddings.append(response["embedding"])
            else:
                raise ValueError(f"Неожиданный формат ответа Yandex: {response}")
        return all_embeddings

    def chat(self, prompt: str) -> str:
        """Генерация ответа от YandexGPT."""
        headers = self._headers()
        url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

        messages = [
            {
                "role": "system",
                "text": "Ты точный технический ассистент. Отвечай строго по контексту.",
            },
            {"role": "user", "text": prompt},
        ]
        payload = {
            "modelUri": self.chat_model,
            "completionOptions": {"stream": False, "temperature": 0.2},
            "messages": messages,
        }

        r = requests.post(
            url,
            headers=headers,
            json=payload,
            verify=SSL_VERIFY,
        )
        r.raise_for_status()
        response = r.json()

        return (
            response.get("result", {})
            .get("alternatives", [{}])[0]
            .get("message", {})
            .get("text", "")
        )


ai = YandexAIProvider()


# ==================== ОБРАБОТКА ФАЙЛОВ ====================
def extract_text(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    try:
        if ext == ".pdf":
            return "\n".join(
                page.extract_text() or "" for page in pypdf.PdfReader(file_path).pages
            )
        elif ext == ".docx":
            return "\n".join(p.text for p in Document(file_path).paragraphs)
        elif ext == ".xlsx":
            return "\n".join(
                " ".join(str(c) for c in row if c)
                for sheet in openpyxl.load_workbook(file_path, data_only=True)
                for row in sheet.iter_rows(values_only=True)
            )
        return ""
    except Exception as e:
        logger.error(f"Ошибка чтения {file_path}: {e}")
        return ""


def chunk_text(text: str, source: str) -> List[dict]:
    if not text.strip():
        return []
    words, chunks, i = text.split(), [], 0
    while i < len(words):
        end = min(i + CHUNK_SIZE, len(words))
        chunk = " ".join(words[i:end])
        chunks.append(
            {
                "text": chunk,
                "source": source,
                "id": f"{source}_{hashlib.md5(chunk.encode()).hexdigest()[:8]}",
            }
        )
        i += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


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
                        embeddings=ai.embed(docs[i : i + 50]),
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Запуск приложения. Провайдер: Yandex AI Studio")
    scheduler.add_job(
        run_index_job,
        IntervalTrigger(minutes=INDEX_INTERVAL),
        id="index_job",
        replace_existing=True,
    )
    scheduler.start()
    yield
    logger.info("🛑 Остановка приложения...")
    scheduler.shutdown(wait=False)


# ==================== FASTAPI APP ====================
app = FastAPI(title="DocSearch MVP", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = f"{(time.time() - start):.2f}s"
    logger.info(
        f"{request.method} {request.url.path} | {response.status_code} | {duration}"
    )
    return response


@app.get("/api/health")
async def health(request: Request):
    """Возвращает HTML при открытии в браузере, JSON для API."""
    accept = request.headers.get("accept", "")

    try:
        count = collection.count()
        data = {
            "status": "healthy",
            "provider": "yandex",
            "indexed_documents": count,
            "scheduler_running": scheduler.running,
            "uptime_seconds": round(time.time() - start_time, 1),
        }
    except Exception as e:
        if "text/html" in accept:
            return HTMLResponse(content=_health_error_html(str(e)), status_code=503)
        raise HTTPException(503, f"Unhealthy: {str(e)}")

    # Если запрос из браузера — возвращаем красивую HTML страницу
    if "text/html" in accept:
        return HTMLResponse(content=_health_html(data))

    # Иначе возвращаем JSON
    return data


def _format_uptime(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)} сек"
    elif seconds < 3600:
        return f"{int(seconds // 60)} мин"
    elif seconds < 86400:
        return f"{int(seconds // 3600)} ч {int((seconds % 3600) // 60)} мин"
    else:
        return f"{int(seconds // 86400)} д {int((seconds % 86400) // 3600)} ч"


def _health_html(data: dict) -> str:
    return f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DocSearch — Статус системы</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 2rem;
        }}
        .container {{
            max-width: 600px;
            width: 100%;
        }}
        .card {{
            background: white;
            border-radius: 20px;
            padding: 3rem;
            box-shadow: 0 20px 60px rgba(0,0,0,0.15);
        }}
        .header {{
            text-align: center;
            margin-bottom: 2.5rem;
        }}
        .header h1 {{
            font-size: 2rem;
            color: #1f2937;
            margin-bottom: 0.5rem;
        }}
        .status-badge {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.75rem 1.5rem;
            border-radius: 50px;
            font-weight: 600;
            font-size: 1.1rem;
            margin-top: 1rem;
        }}
        .status-badge.healthy {{
            background: #10b981;
            color: white;
            box-shadow: 0 4px 15px rgba(16, 185, 129, 0.4);
        }}
        .status-badge.unhealthy {{
            background: #ef4444;
            color: white;
            box-shadow: 0 4px 15px rgba(239, 68, 68, 0.4);
        }}
        .metrics {{
            display: grid;
            gap: 1.5rem;
        }}
        .metric {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1.25rem 1.5rem;
            background: #f9fafb;
            border-radius: 12px;
            transition: transform 0.2s;
        }}
        .metric:hover {{
            transform: translateX(5px);
            background: #f3f4f6;
        }}
        .metric-label {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            color: #6b7280;
            font-weight: 500;
        }}
        .metric-icon {{
            font-size: 1.5rem;
        }}
        .metric-value {{
            font-size: 1.25rem;
            font-weight: 700;
            color: #1f2937;
        }}
        .footer {{
            text-align: center;
            margin-top: 2rem;
            padding-top: 1.5rem;
            border-top: 1px solid #e5e7eb;
            color: #9ca3af;
            font-size: 0.875rem;
        }}
        .footer a {{
            color: #667eea;
            text-decoration: none;
            font-weight: 500;
        }}
        .footer a:hover {{
            text-decoration: underline;
        }}
        .refresh {{
            display: block;
            margin: 1.5rem auto 0;
            padding: 0.75rem 2rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .refresh:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(102,126,234,0.4);
        }}
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(10px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        .card {{ animation: fadeIn 0.3s ease-out; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="header">
                <h1>🔍 DocSearch</h1>
                <p style="color: #6b7280;">Статус системы семантического поиска</p>
                <div class="status-badge {"healthy" if data["status"] == "healthy" else "unhealthy"}">
                    {"✅ Система работает" if data["status"] == "healthy" else "❌ Проблема"}
                </div>
            </div>

            <div class="metrics">
                <div class="metric">
                    <div class="metric-label">
                        <span class="metric-icon">📚</span>
                        <span>Проиндексировано документов</span>
                    </div>
                    <div class="metric-value">{data["indexed_documents"]:,}</div>
                </div>

                <div class="metric">
                    <div class="metric-label">
                        <span class="metric-icon">⚡</span>
                        <span>AI Провайдер</span>
                    </div>
                    <div class="metric-value" style="text-transform: capitalize;">{data["provider"]}</div>
                </div>

                <div class="metric">
                    <div class="metric-label">
                        <span class="metric-icon">⏱️</span>
                        <span>Аптайм</span>
                    </div>
                    <div class="metric-value">{_format_uptime(data["uptime_seconds"])}</div>
                </div>

                <div class="metric">
                    <div class="metric-label">
                        <span class="metric-icon">🔄</span>
                        <span>Фоновая индексация</span>
                    </div>
                    <div class="metric-value" style="color: {"#10b981" if data["scheduler_running"] else "#ef4444"};">
                        {"✅ Активна" if data["scheduler_running"] else "⏸️ Остановлена"}
                    </div>
                </div>
            </div>

            <button class="refresh" onclick="location.reload()">🔄 Обновить</button>

            <div class="footer">
                <a href="/dashboard">📊 Полный дашборд</a> ·
                <a href="/api/health?format=json">📄 JSON API</a> ·
                <a href="/docs">📖 Swagger</a>
            </div>
        </div>
    </div>

    <script>
        // Автоматическое обновление каждые 30 секунд
        setTimeout(() => location.reload(), 30000);
    </script>
</body>
</html>
    """


def _health_error_html(error: str) -> str:
    return f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DocSearch — Ошибка</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 2rem;
        }}
        .card {{
            background: white;
            border-radius: 20px;
            padding: 3rem;
            box-shadow: 0 20px 60px rgba(0,0,0,0.15);
            text-align: center;
            max-width: 500px;
        }}
        .icon {{ font-size: 4rem; margin-bottom: 1rem; }}
        h1 {{ color: #ef4444; margin-bottom: 1rem; }}
        p {{ color: #6b7280; line-height: 1.6; }}
        .error {{
            background: #fee2e2;
            padding: 1rem;
            border-radius: 8px;
            margin-top: 1rem;
            color: #991b1b;
            font-family: monospace;
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">❌</div>
        <h1>Система недоступна</h1>
        <p>Произошла ошибка при проверке статуса системы</p>
        <div class="error">{error}</div>
    </div>
</body>
</html>
    """


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    """Красивая страница дашборда с метриками."""
    html = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DocSearch Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 2rem;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .header {
            text-align: center;
            color: white;
            margin-bottom: 2rem;
        }
        .header h1 {
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }
        .header p {
            font-size: 1.1rem;
            opacity: 0.9;
        }
        .status-badge {
            display: inline-block;
            padding: 0.5rem 1.5rem;
            border-radius: 50px;
            font-weight: 600;
            margin-top: 1rem;
            font-size: 1.1rem;
        }
        .status-badge.healthy {
            background: #10b981;
            color: white;
            box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4);
        }
        .status-badge.unhealthy {
            background: #ef4444;
            color: white;
            box-shadow: 0 4px 12px rgba(239, 68, 68, 0.4);
        }
        .cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }
        .card {
            background: white;
            border-radius: 16px;
            padding: 2rem;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 15px 40px rgba(0,0,0,0.15);
        }
        .card-icon {
            font-size: 2.5rem;
            margin-bottom: 1rem;
        }
        .card-label {
            color: #6b7280;
            font-size: 0.9rem;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
        }
        .card-value {
            color: #1f2937;
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 0.25rem;
        }
        .card-subtext {
            color: #9ca3af;
            font-size: 0.85rem;
        }
        .progress-bar {
            width: 100%;
            height: 8px;
            background: #e5e7eb;
            border-radius: 4px;
            overflow: hidden;
            margin-top: 1rem;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea, #764ba2);
            transition: width 0.3s;
        }
        .api-section {
            background: white;
            border-radius: 16px;
            padding: 2rem;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }
        .api-section h2 {
            color: #1f2937;
            margin-bottom: 1.5rem;
            font-size: 1.5rem;
        }
        .endpoint {
            background: #f9fafb;
            border-left: 4px solid #667eea;
            padding: 1rem 1.5rem;
            margin-bottom: 1rem;
            border-radius: 8px;
        }
        .endpoint-method {
            display: inline-block;
            background: #667eea;
            color: white;
            padding: 0.25rem 0.75rem;
            border-radius: 4px;
            font-weight: 600;
            font-size: 0.85rem;
            margin-right: 0.5rem;
        }
        .endpoint-path {
            font-family: 'Courier New', monospace;
            color: #1f2937;
            font-weight: 600;
        }
        .endpoint-desc {
            color: #6b7280;
            margin-top: 0.5rem;
            font-size: 0.9rem;
        }
        .refresh-btn {
            position: fixed;
            bottom: 2rem;
            right: 2rem;
            background: white;
            border: none;
            border-radius: 50%;
            width: 60px;
            height: 60px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            cursor: pointer;
            font-size: 1.5rem;
            transition: transform 0.3s;
        }
        .refresh-btn:hover {
            transform: rotate(180deg);
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .loading {
            animation: pulse 1.5s ease-in-out infinite;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 DocSearch Dashboard</h1>
            <p>Мониторинг системы семантического поиска</p>
            <div id="statusBadge" class="status-badge loading">Загрузка...</div>
        </div>

        <div class="cards">
            <div class="card">
                <div class="card-icon">📚</div>
                <div class="card-label">Проиндексировано</div>
                <div class="card-value" id="docCount">—</div>
                <div class="card-subtext">документов в базе</div>
                <div class="progress-bar">
                    <div class="progress-fill" id="docProgress" style="width: 0%"></div>
                </div>
            </div>

            <div class="card">
                <div class="card-icon">⚡</div>
                <div class="card-label">AI Провайдер</div>
                <div class="card-value" id="provider">—</div>
                <div class="card-subtext">Yandex AI Studio</div>
            </div>

            <div class="card">
                <div class="card-icon">⏱️</div>
                <div class="card-label">Аптайм</div>
                <div class="card-value" id="uptime">—</div>
                <div class="card-subtext">время работы</div>
            </div>

            <div class="card">
                <div class="card-icon">🔄</div>
                <div class="card-label">Планировщик</div>
                <div class="card-value" id="scheduler">—</div>
                <div class="card-subtext" id="schedulerText">фоновая индексация</div>
            </div>
        </div>

        <div class="api-section">
            <h2>🔌 API Endpoints</h2>
            <div class="endpoint">
                <span class="endpoint-method">GET</span>
                <span class="endpoint-path">/api/health</span>
                <div class="endpoint-desc">Проверка статуса системы и получение метрик</div>
            </div>
            <div class="endpoint">
                <span class="endpoint-method">GET</span>
                <span class="endpoint-path">/api/ready</span>
                <div class="endpoint-desc">Количество проиндексированных документов</div>
            </div>
            <div class="endpoint">
                <span class="endpoint-method">POST</span>
                <span class="endpoint-path">/api/index</span>
                <div class="endpoint-desc">Запуск ручной индексации документов</div>
            </div>
            <div class="endpoint">
                <span class="endpoint-method">POST</span>
                <span class="endpoint-path">/api/query</span>
                <div class="endpoint-desc">Поиск и генерация ответа на вопрос</div>
            </div>
        </div>
    </div>

    <button class="refresh-btn" onclick="loadMetrics()" title="Обновить">🔄</button>

    <script>
        function formatUptime(seconds) {
            if (seconds < 60) return Math.round(seconds) + 'с';
            if (seconds < 3600) return Math.round(seconds / 60) + 'м';
            if (seconds < 86400) return Math.round(seconds / 3600) + 'ч';
            return Math.round(seconds / 86400) + 'д';
        }

        async function loadMetrics() {
            try {
                const response = await fetch('/api/health');
                const data = await response.json();

                const badge = document.getElementById('statusBadge');
                badge.className = 'status-badge ' + (data.status === 'healthy' ? 'healthy' : 'unhealthy');
                badge.textContent = data.status === 'healthy' ? '✅ Система работает' : '❌ Проблема';

                document.getElementById('docCount').textContent = data.indexed_documents.toLocaleString();
                document.getElementById('docProgress').style.width = Math.min(data.indexed_documents / 10, 100) + '%';

                document.getElementById('provider').textContent = data.provider.charAt(0).toUpperCase() + data.provider.slice(1);

                document.getElementById('uptime').textContent = formatUptime(data.uptime_seconds);

                document.getElementById('scheduler').textContent = data.scheduler_running ? '✅ Активен' : '⏸️ Остановлен';
                document.getElementById('schedulerText').textContent = data.scheduler_running ? 'индексация по расписанию' : 'не запущен';
            } catch (error) {
                document.getElementById('statusBadge').className = 'status-badge unhealthy';
                document.getElementById('statusBadge').textContent = '❌ Нет связи';
            }
        }

        loadMetrics();
        setInterval(loadMetrics, 30000);
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html)


class QueryRequest(BaseModel):
    question: str


@app.post("/api/index")
def trigger_index():
    if not index_lock.acquire(blocking=False):
        return {"status": "running", "message": "Индексация уже выполняется"}
    try:
        logger.info("🚀 Запуск индексации...")
        count = index_documents()
        return {"status": "success", "indexed_files": count}
    except Exception as e:
        logger.error(f"❌ Ошибка индексации: {e}", exc_info=True)
        raise HTTPException(500, str(e))
    finally:
        index_lock.release()


@app.get("/api/ready")
def ready():
    return {"status": "ok", "indexed_count": collection.count()}


@app.post("/api/query")
def query(req: QueryRequest):
    if not req.question.strip():
        raise HTTPException(400, "Вопрос пустой")
    logger.info(f"❓ Запрос: {req.question}")

    try:
        q_emb = ai.embed([req.question], is_query=True)[0]
        res = collection.query(query_embeddings=[q_emb], n_results=TOP_K)
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
        answer = ai.chat(prompt)
        sources = list(set(m["source"] for m in res["metadatas"][0]))
        return {"answer": answer, "sources": sources}
    except Exception as e:
        raise HTTPException(500, f"Ошибка генерации ответа: {str(e)}")
