#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ============================================================
# VANY IA - GEMINI PROVIDER V06.0
# ============================================================

import os
import json
import urllib.request
import urllib.error


class GeminiProvider:

    def __init__(self):

        self.api_key = os.getenv(
            "GEMINI_API_KEY",
            ""
        ).strip()

        self.model = os.getenv(
            "GEMINI_MODEL",
            "gemini-2.5-flash"
        ).strip()


    def configurado(self):

        return bool(
            self.api_key
        )


    def info(self):

        return {
            "provider": "gemini",
            "model": self.model,
            "configured": self.configurado()
        }


    def responder(
        self,
        mensagem,
        image=None
    ):

        if not self.configurado():

            raise RuntimeError(
                "GEMINI_API_KEY não configurada."
            )


        url = (
            "https://generativelanguage.googleapis.com/"
            "v1beta/models/"
            + self.model
            + ":generateContent?key="
            + self.api_key
        )


        partes = []


        if mensagem:

            partes.append({
                "text": str(mensagem)
            })


        if image:

            # A imagem poderá ser integrada
            # posteriormente com o formato
            # multimodal oficial do Gemini.
            #
            # Por enquanto não enviamos uma URL
            # diretamente como texto para evitar
            # uma requisição inválida.
            partes.append({
                "text":
                    "\nImagem recebida para análise."
            })


        if not partes:

            partes.append({
                "text":
                    "Responda ao usuário."
            })


        payload = {

            "contents": [

                {
                    "parts": partes
                }

            ]

        }


        dados = json.dumps(
            payload
        ).encode("utf-8")


        requisicao = urllib.request.Request(

            url,

            data=dados,

            headers={
                "Content-Type":
                    "application/json"
            },

            method="POST"
        )


        try:

            with urllib.request.urlopen(
                requisicao,
                timeout=60
            ) as resposta:

                corpo = (
                    resposta
                    .read()
                    .decode("utf-8")
                )


            resultado = json.loads(
                corpo
            )


        except urllib.error.HTTPError as erro:

            corpo = (
                erro
                .read()
                .decode(
                    "utf-8",
                    errors="replace"
                )
            )

            raise RuntimeError(
                "Gemini HTTP "
                + str(erro.code)
                + ": "
                + corpo[:1000]
            )


        except urllib.error.URLError as erro:

            raise RuntimeError(
                "Erro de conexão com Gemini: "
                + str(erro.reason)
            )


        candidatos = resultado.get(
            "candidates",
            []
        )


        if not candidatos:

            raise RuntimeError(
                "Gemini não retornou candidatos."
            )


        try:

            partes_resposta = (
                candidatos[0]
                ["content"]
                ["parts"]
            )

        except (
            KeyError,
            IndexError,
            TypeError
        ):

            raise RuntimeError(
                "Resposta Gemini inválida."
            )


        textos = []


        for parte in partes_resposta:

            if isinstance(
                parte,
                dict
            ):

                texto = parte.get(
                    "text"
                )

                if texto:

                    textos.append(
                        str(texto)
                    )


        resposta_final = (
            "\n".join(textos)
            .strip()
        )


        if not resposta_final:

            raise RuntimeError(
                "Gemini retornou resposta vazia."
            )


        return resposta_final
