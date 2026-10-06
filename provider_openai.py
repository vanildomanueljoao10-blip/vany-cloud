import os
import requests


class OpenAIProvider:

    def __init__(self):

        self.api_key = os.getenv(
            "OPENAI_API_KEY",
            ""
        ).strip()

        self.model = os.getenv(
            "OPENAI_MODEL",
            "gpt-5-mini"
        ).strip()

        self.url = (
            "https://api.openai.com/v1/responses"
        )

    def configurado(self):

        return bool(
            self.api_key
        )

    def info(self):

        return {
            "provider": "openai",
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
                "OPENAI_API_KEY não configurada."
            )

        headers = {

            "Authorization":
                "Bearer " + self.api_key,

            "Content-Type":
                "application/json"
        }

        if image:

            raise RuntimeError(
                "Imagem ainda não está "
                "habilitada neste adapter OpenAI."
            )

        payload = {

            "model":
                self.model,

            "input":
                str(prompt)
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

                "OpenAI HTTP "
                + str(response.status_code)
                + ": "
                + str(detalhe)
            )

        try:

            dados = response.json()

        except Exception as erro:

            raise RuntimeError(
                "Resposta JSON inválida da OpenAI: "
                + str(erro)
            )

        resposta = dados.get(
            "output_text",
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
                "OpenAI retornou uma resposta vazia."
            )

        return resposta
