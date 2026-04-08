"""Конфигурация приложения и логирование."""

import logging
import logging.handlers
import os
import threading
import time

import chromadb
from dotenv import load_dotenv

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

# ==================== ЗАГРУЗКА .ENV ====================
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

# ==================== CHROMA DB ====================
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(name="tech_docs")
index_lock = threading.Lock()

# Экспортируем TOP_K для использования в routes
__all__ = [
    "logger",
    "start_time",
    "DOC_DIR",
    "DWG_CACHE_DIR",
    "DWG_CONVERTER_CMD",
    "CHUNK_SIZE",
    "CHUNK_OVERLAP",
    "TOP_K",
    "INDEX_INTERVAL",
    "SSL_VERIFY",
    "chroma_client",
    "collection",
    "index_lock",
]
