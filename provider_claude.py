import os
import requests


class ClaudeProvider:

    def __init__(self):

        self.api_key = os.getenv(
            "ANTHROPIC_API_KEY",
            ""
        ).strip()

        self.model = os.getenv(
            "ANTHROPIC_MODEL",
            "claude-sonnet-5"
        ).strip()

        self.url = (
            "https://api.anthropic.com/v1/messages"
        )

    def configurado(self):

        return bool(
            self.api_key
        )

    def info(self):

        return {
            "provider": "claude",
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
                "ANTHROPIC_API_KEY não configurada."
            )

        if image:

            raise RuntimeError(
                "Imagem ainda não está "
                "habilitada neste adapter Claude."
            )

        headers = {

            "x-api-key":
                self.api_key,

            "anthropic-version":
                "2023-06-01",

            "content-type":
                "application/json"
        }

        payload = {

            "model":
                self.model,

            "max_tokens":
                2048,

            "messages": [

                {
                    "role":
                        "user",

                    "content":
                        str(prompt)
                }

            ]
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

                "Claude HTTP "
                + str(response.status_code)
                + ": "
                + str(detalhe)
            )

        try:

            dados = response.json()

        except Exception as erro:

            raise RuntimeError(
                "Resposta JSON inválida do Claude: "
                + str(erro)
            )

        content = dados.get(
            "content",
            []
        )

        if not isinstance(
            content,
            list
        ):

            raise RuntimeError(
                "Claude retornou content inválido."
            )

        partes = []

        for bloco in content:

            if not isinstance(
                bloco,
                dict
            ):

                continue

            if bloco.get(
                "type"
            ) != "text":

                continue

            texto = bloco.get(
                "text",
                ""
            )

            if isinstance(
                texto,
                str
            ):

                texto = texto.strip()

                if texto:

                    partes.append(
                        texto
                    )

        resposta = "\n".join(
            partes
        ).strip()

        if not resposta:

            raise RuntimeError(
                "Claude retornou uma resposta vazia."
            )

        return resposta
