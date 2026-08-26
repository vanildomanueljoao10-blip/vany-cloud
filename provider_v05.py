#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ============================================================
# VANY IA - PROVIDER MANAGER V05.6
# Local + Gemini + OpenRouter
# ============================================================

from gemini_provider import GeminiProvider
from openrouter_provider import OpenRouterProvider


class ProviderManager:

    def __init__(self):

        self.gemini = GeminiProvider()
        self.openrouter = OpenRouterProvider()

        # OpenRouter será o provider padrão
        self.provider = "openrouter"
        self.model = self.openrouter.model


    def info(self):

        if self.provider == "gemini":

            info = self.gemini.info()

            return {
                "provider": "gemini",
                "model": info.get(
                    "model",
                    self.gemini.model
                ),
                "configured": info.get(
                    "configured",
                    False
                )
            }


        if self.provider == "openrouter":

            info = self.openrouter.info()

            return {
                "provider": "openrouter",
                "model": info.get(
                    "model",
                    self.openrouter.model
                ),
                "configured": info.get(
                    "configured",
                    False
                )
            }


        return {
            "provider": "local",
            "model": "local",
            "configured": True
        }


    def is_local(self):

        return self.provider == "local"


    def is_online(self):

        return self.provider in (
            "gemini",
            "openrouter"
        )


    def selecionar(
        self,
        provider,
        model="auto"
    ):

        provider = str(
            provider
        ).lower().strip()


        if provider == "local":

            self.provider = "local"
            self.model = "local"

            return self.info()


        if provider == "gemini":

            self.provider = "gemini"

            if model == "auto":

                self.model = self.gemini.model

            else:

                self.model = str(
                    model
                ).strip()

            self.gemini.model = self.model

            return self.info()


        if provider == "openrouter":

            self.provider = "openrouter"

            if model == "auto":

                self.model = self.openrouter.model

            else:

                self.model = str(
                    model
                ).strip()

            self.openrouter.model = self.model

            return self.info()


        raise ValueError(
            "Provider não suportado: "
            + provider
        )


    def responder_online(
        self,
        mensagem
    ):

        if self.provider == "gemini":

            return self.gemini.responder(
                mensagem
            )


        if self.provider == "openrouter":

            return self.openrouter.responder(
                mensagem
            )


        raise RuntimeError(
            "O provider atual não é online."
        )


    def responder(
        self,
        mensagem
    ):

        if self.provider == "local":

            raise RuntimeError(
                "O provider local deve ser "
                "processado pelo VanyEngineV05."
            )

        return self.responder_online(
            mensagem
        )
