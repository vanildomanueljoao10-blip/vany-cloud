#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import urllib.request
import urllib.error


class OpenRouterProvider:

    URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self):

        self.api_key = os.getenv(
            "OPENROUTER_API_KEY",
            ""
        ).strip()

        self.model = os.getenv(
            "OPENROUTER_MODEL",
            "openrouter/free"
        ).strip()

    def configurado(self):

        return bool(self.api_key)

    def info(self):

        return {
            "provider": "openrouter",
            "model": self.model,
            "configured": self.configurado()
        }

    def responder(self, mensagem):

        if not self.configurado():

            raise RuntimeError(
                "OPENROUTER_API_KEY não configurada."
            )

        dados = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": mensagem
                }
            ]
        }

        corpo = json.dumps(
            dados
        ).encode("utf-8")

        requisicao = urllib.request.Request(
            self.URL,
            data=corpo,
            headers={
                "Authorization":
                    "Bearer " + self.api_key,

                "Content-Type":
                    "application/json",

                "HTTP-Referer":
                    "http://localhost",

                "X-Title":
                    "Vany IA"
            },
            method="POST"
        )

        try:

            with urllib.request.urlopen(
                requisicao,
                timeout=60
            ) as resposta:

                texto = resposta.read().decode(
                    "utf-8"
                )

        except urllib.error.HTTPError as erro:

            erro_texto = erro.read().decode(
                "utf-8",
                errors="replace"
            )

            raise RuntimeError(
                "OpenRouter HTTP "
                + str(erro.code)
                + ": "
                + erro_texto
            )

        except urllib.error.URLError as erro:

            raise RuntimeError(
                "Erro de conexão com OpenRouter: "
                + str(erro.reason)
            )

        try:

            resultado = json.loads(texto)

        except json.JSONDecodeError:

            raise RuntimeError(
                "Resposta inválida do OpenRouter."
            )

        escolhas = resultado.get(
            "choices",
            []
        )

        if not escolhas:

            raise RuntimeError(
                "OpenRouter não retornou resposta."
            )

        mensagem_resultado = escolhas[0].get(
            "message",
            {}
        )

        resposta = mensagem_resultado.get(
            "content",
            ""
        )

        if isinstance(resposta, list):

            partes = []

            for parte in resposta:

                if isinstance(parte, dict):

                    valor = parte.get(
                        "text",
                        ""
                    )

                    if valor:
                        partes.append(valor)

            resposta = "".join(partes)

        resposta = str(
            resposta
        ).strip()

        if not resposta:

            raise RuntimeError(
                "OpenRouter retornou resposta vazia."
            )

        return resposta
