from openai import OpenAI

from app.config import settings

LOTE_MAXIMO = 100


class EmbeddingService:
    def __init__(self, client: OpenAI | None = None):
        self.client = client or OpenAI(api_key=settings.openai_api_key)
        self.modelo = settings.embedding_model
        self.dimensoes = settings.embedding_dimensions

    def gerar(self, textos: list[str]) -> list[list[float]]:
        vetores: list[list[float]] = []
        for inicio in range(0, len(textos), LOTE_MAXIMO):
            lote = textos[inicio : inicio + LOTE_MAXIMO]
            resposta = self.client.embeddings.create(
                model=self.modelo, input=lote, dimensions=self.dimensoes
            )
            vetores.extend(item.embedding for item in resposta.data)
        return vetores

    def gerar_um(self, texto: str) -> list[float]:
        return self.gerar([texto])[0]
