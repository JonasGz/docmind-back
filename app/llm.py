import json
import logging

from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)

LOTE_MAXIMO = 100


class Modelo:
    def __init__(self, client: OpenAI | None = None):
        self._client = client
        self.modelo_embedding = settings.embedding_model
        self.dimensoes = settings.embedding_dimensions

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(api_key=settings.openai_api_key)
        return self._client

    def completar(self, mensagens: list[dict[str, str]]) -> str:
        resposta = self.client.chat.completions.create(
            model=settings.llm_model, messages=mensagens
        )
        return resposta.choices[0].message.content or ""

    def completar_json(self, prompt: str) -> dict:
        resposta = self.client.chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        return json.loads(resposta.choices[0].message.content or "{}")

    def embutir(self, textos: list[str]) -> list[list[float]]:
        vetores: list[list[float]] = []
        for inicio in range(0, len(textos), LOTE_MAXIMO):
            lote = textos[inicio : inicio + LOTE_MAXIMO]
            resposta = self.client.embeddings.create(
                model=self.modelo_embedding, input=lote, dimensions=self.dimensoes
            )
            vetores.extend(item.embedding for item in resposta.data)
        return vetores

    def embutir_um(self, texto: str) -> list[float]:
        return self.embutir([texto])[0]
