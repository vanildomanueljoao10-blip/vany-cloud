import os
import requests


class GroqProvider:

    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY", "").strip()

        self.model = os.getenv(
            "GROQ_MODEL",
            "openai/gpt-oss-120b"
        ).strip()

        self.url = (
            "https://api.groq.com/openai/v1/chat/completions"
        )

    def configurado(self):
        return bool(self.api_key)

    def info(self):
        return {
            "provider": "groq",
            "model": self.model,
            "configured": self.configurado()
        }

    def responder(self, prompt, image=None, images=None):

        if not self.configurado():
            raise RuntimeError(
                "GROQ_API_KEY não configurada."
            )

        if image or images:
            raise RuntimeError(
                "O provider Groq desta versão aceita texto, "
                "mas ainda não tem suporte a imagens."
            )

        headers = {
            "Authorization": "Bearer " + self.api_key,
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": str(prompt)
                }
            ],
            "temperature": 0.7,
            "max_completion_tokens": 2048,
            "stream": False
        }

        try:
            response = requests.post(
                self.url,
                headers=headers,
                json=payload,
                timeout=120
            )
        except requests.RequestException as erro:
            raise RuntimeError(
                "Falha de ligação à Groq: " + str(erro)
            )

        if response.status_code != 200:
            try:
                detalhe = response.json()
            except Exception:
                detalhe = response.text

            raise RuntimeError(
                "Groq HTTP "
                + str(response.status_code)
                + ": "
                + str(detalhe)
            )

        try:
            dados = response.json()
        except Exception as erro:
            raise RuntimeError(
                "Resposta JSON inválida da Groq: "
                + str(erro)
            )

        choices = dados.get("choices", [])

        if not choices:
            raise RuntimeError(
                "Groq não devolveu nenhuma resposta."
            )

        mensagem = choices[0].get("message", {})
        resposta = mensagem.get("content", "")

        if not isinstance(resposta, str):
            resposta = str(resposta)

        resposta = resposta.strip()

        if not resposta:
            raise RuntimeError(
                "Groq devolveu uma resposta vazia."
            )

        return resposta
