"""Yandex AI Studio Provider — эмбеддинги и генерация ответов."""
import os
from typing import List

import requests

from config import SSL_VERIFY, logger


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
