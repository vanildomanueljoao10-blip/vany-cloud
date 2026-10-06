import os
import json
import requests


class DeepSeekProvider:

    def __init__(self):

        self.api_key = os.getenv(
            "DEEPSEEK_API_KEY",
            ""
        ).strip()

        self.model = os.getenv(
            "DEEPSEEK_MODEL",
            "deepseek-v4-flash"
        ).strip()

        self.url = (
            "https://api.deepseek.com/chat/completions"
        )

    def configurado(self):

        return bool(
            self.api_key
        )

    def info(self):

        return {
            "provider": "deepseek",
            "model": self.model,
            "configured": self.configurado()
        }

    def responder(
        self,
        prompt,
        image=None
    ):

        if not self.configurado():

            raise RuntimeError(
                "DEEPSEEK_API_KEY não configurada."
            )

        if image:

            raise RuntimeError(
                "O provider DeepSeek configurado "
                "para esta rota ainda não aceita imagem."
            )

        headers = {

            "Authorization":
                "Bearer " + self.api_key,

            "Content-Type":
                "application/json"

        }

        payload = {

            "model":
                self.model,

            "messages": [

                {
                    "role":
                        "user",

                    "content":
                        str(prompt)
                }

            ],

            "stream":
                False
        }

        response = requests.post(

            self.url,

            headers=headers,

            json=payload,

            timeout=60
        )

        if response.status_code != 200:

            try:

                detalhe = response.json()

            except Exception:

                detalhe = response.text

            raise RuntimeError(

                "DeepSeek HTTP "
                + str(response.status_code)
                + ": "
                + str(detalhe)

            )

        try:

            dados = response.json()

        except Exception as erro:

            raise RuntimeError(
                "Resposta JSON inválida do DeepSeek: "
                + str(erro)
            )

        choices = dados.get(
            "choices",
            []
        )

        if not choices:

            raise RuntimeError(
                "DeepSeek não retornou choices."
            )

        message = choices[0].get(
            "message",
            {}
        )

        resposta = message.get(
            "content",
            ""
        )

        if not isinstance(
            resposta,
            str
        ):

            resposta = str(
                resposta
            )

        resposta = resposta.strip()

        if not resposta:

            raise RuntimeError(
                "DeepSeek retornou uma resposta vazia."
            )

        return resposta
