import os
import base64
import requests


class OpenRouterProvider:

    def __init__(self):
        self.api_key = os.getenv(
            "OPENROUTER_API_KEY",
            ""
        ).strip()

        self.model = os.getenv(
            "OPENROUTER_VISION_MODEL",
            "google/gemini-2.5-flash"
        )

        self.stt_model = os.getenv(
            "OPENROUTER_STT_MODEL",
            "openai/whisper-1"
        )

        self.tts_model = os.getenv(
            "OPENROUTER_TTS_MODEL",
            "openai/gpt-4o-mini-tts-2025-12-15"
        )

        self.tts_voice = os.getenv(
            "OPENROUTER_TTS_VOICE",
            "alloy"
        )

        self.chat_url = (
            "https://openrouter.ai/api/v1/chat/completions"
        )

        self.stt_url = (
            "https://openrouter.ai/api/v1/audio/transcriptions"
        )

        self.tts_url = (
            "https://openrouter.ai/api/v1/audio/speech"
        )

    def configurado(self):
        return bool(self.api_key)

    def info(self):
        return {
            "provider": "openrouter",
            "model": self.model,
            "configured": self.configurado()
        }

    def _headers(self):
        return {
            "Authorization": "Bearer " + self.api_key,
            "Content-Type": "application/json"
        }

    def responder(
        self,
        prompt,
        image=None,
        images=None
    ):

        if not self.configurado():
            raise RuntimeError(
                "OPENROUTER_API_KEY não configurada"
            )

        prompt = str(prompt or "").strip()

        if not prompt:
            prompt = (
                "Analise o conteúdo enviado e "
                "responda de forma clara."
            )

        content = [
            {
                "type": "text",
                "text": prompt
            }
        ]

        imagens = []

        if images:
            for imagem in images:
                if imagem:
                    imagens.append(imagem)

        elif image:
            imagens.append(image)

        for imagem in imagens:

            if not isinstance(imagem, str):
                continue

            imagem = imagem.strip()

            if not imagem:
                continue

            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": imagem
                    }
                }
            )

        if len(content) == 1:

            payload_content = prompt

        else:

            payload_content = content

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": payload_content
                }
            ],
            "max_tokens": 4096
        }

        try:

            resposta = requests.post(
                self.chat_url,
                headers=self._headers(),
                json=payload,
                timeout=90
            )

        except requests.RequestException as erro:

            raise RuntimeError(
                "Falha de conexão com OpenRouter: "
                + str(erro)
            ) from erro

        if resposta.status_code != 200:

            raise RuntimeError(
                "OpenRouter HTTP "
                + str(resposta.status_code)
                + ": "
                + resposta.text[:1000]
            )

        try:

            dados = resposta.json()

        except Exception as erro:

            raise RuntimeError(
                "OpenRouter retornou JSON inválido: "
                + str(erro)
            ) from erro

        try:

            texto = dados[
                "choices"
            ][0][
                "message"
            ][
                "content"
            ]

        except Exception:

            raise RuntimeError(
                "Resposta inesperada do OpenRouter: "
                + str(dados)[:1000]
            )

        if isinstance(texto, list):

            partes = []

            for item in texto:

                if not isinstance(item, dict):
                    continue

                if item.get("type") == "text":

                    partes.append(
                        str(
                            item.get(
                                "text",
                                ""
                            )
                        )
                    )

            texto = "\n".join(partes)

        texto = str(texto or "").strip()

        if not texto:

            raise RuntimeError(
                "O modelo retornou uma resposta vazia"
            )

        return texto

    def transcrever_audio(
        self,
        audio_base64,
        formato="m4a"
    ):

        if not self.configurado():
            raise RuntimeError(
                "OPENROUTER_API_KEY não configurada"
            )

        audio_base64 = str(
            audio_base64 or ""
        ).strip()

        if not audio_base64:

            raise RuntimeError(
                "Áudio vazio"
            )

        formato = str(
            formato or "m4a"
        ).lower().strip()

        formatos_validos = {
            "wav",
            "mp3",
            "flac",
            "m4a",
            "ogg",
            "webm",
            "aac"
        }

        if formato not in formatos_validos:

            formato = "m4a"

        payload = {
            "model": self.stt_model,
            "input_audio": {
                "data": audio_base64,
                "format": formato
            },
            "language": "pt"
        }

        try:

            resposta = requests.post(
                self.stt_url,
                headers=self._headers(),
                json=payload,
                timeout=90
            )

        except requests.RequestException as erro:

            raise RuntimeError(
                "Falha de conexão com STT: "
                + str(erro)
            ) from erro

        if resposta.status_code != 200:

            raise RuntimeError(
                "OpenRouter STT HTTP "
                + str(resposta.status_code)
                + ": "
                + resposta.text[:1000]
            )

        try:

            dados = resposta.json()

        except Exception as erro:

            raise RuntimeError(
                "STT retornou JSON inválido: "
                + str(erro)
            ) from erro

        texto = str(
            dados.get(
                "text",
                ""
            )
        ).strip()

        if not texto:

            raise RuntimeError(
                "A transcrição retornou vazia"
            )

        return texto

    def gerar_voz(self, texto):

        if not self.configurado():

            raise RuntimeError(
                "OPENROUTER_API_KEY não configurada"
            )

        texto = str(
            texto or ""
        ).strip()

        if not texto:

            raise RuntimeError(
                "Texto vazio para TTS"
            )

        payload = {
            "model": self.tts_model,
            "input": texto,
            "voice": self.tts_voice,
            "response_format": "mp3"
        }

        try:

            resposta = requests.post(
                self.tts_url,
                headers=self._headers(),
                json=payload,
                timeout=90
            )

        except requests.RequestException as erro:

            raise RuntimeError(
                "Falha de conexão com TTS: "
                + str(erro)
            ) from erro

        if resposta.status_code != 200:

            raise RuntimeError(
                "OpenRouter TTS HTTP "
                + str(resposta.status_code)
                + ": "
                + resposta.text[:1000]
            )

        if not resposta.content:

            raise RuntimeError(
                "OpenRouter TTS retornou áudio vazio"
            )

        return base64.b64encode(
            resposta.content
        ).decode("utf-8")
