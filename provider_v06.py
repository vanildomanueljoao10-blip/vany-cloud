import os
from engine_v05 import VanyEngineV05

from gemini_provider_router import GeminiProvider
from openrouter_provider import OpenRouterProvider
from provider_openai import OpenAIProvider
from provider_claude import ClaudeProvider
from provider_deepseek import DeepSeekProvider


class ProviderManager:

    def __init__(self):

        self.gemini = GeminiProvider()
        self.openrouter = OpenRouterProvider()
        self.openai = OpenAIProvider()
        self.claude = ClaudeProvider()
        self.deepseek = DeepSeekProvider()

        self.provider = "openrouter"
        self.model = self.openrouter.model

        self.auto_enabled = True

        self.fallback_order = [
            "gemini",
            "openrouter",
            "openai",
            "claude",
            "deepseek",
            "local"
        ]

    # ========================================================
    # INFORMAÇÕES
    # ========================================================

    def info(self):

        if self.provider == "local":

            return {
                "provider": "local",
                "model": "local",
                "configured": True
            }

        if self.provider == "gemini":

            return self.gemini.info()

        if self.provider == "openrouter":

            return self.openrouter.info()

        if self.provider == "openai":

            return self.openai.info()

        if self.provider == "claude":

            return self.claude.info()

        if self.provider == "deepseek":

            return self.deepseek.info()

        if self.provider == "auto":

            return {
                "provider": "auto",
                "model": "vany-auto",
                "configured": True
            }

        return {
            "provider": self.provider,
            "model": self.model,
            "configured": False
        }

    def providers_info(self):

        return {

            "local": {
                "provider": "local",
                "model": "local",
                "configured": True
            },

            "gemini":
                self.gemini.info(),

            "openrouter":
                self.openrouter.info(),

            "openai":
                self.openai.info(),

            "claude":
                self.claude.info(),

            "deepseek":
                self.deepseek.info()
        }

    # ========================================================
    # LOCAL / ONLINE
    # ========================================================

    def is_local(self):

        return self.provider == "local"

    def is_online(self):

        return self.provider in [
            "gemini",
            "openrouter",
            "openai",
            "claude",
            "deepseek"
        ]

    # ========================================================
    # SELECIONAR PROVIDER
    # ========================================================

    def selecionar(
        self,
        provider,
        model="auto"
    ):

        if not isinstance(
            provider,
            str
        ):

            raise ValueError(
                "Provider inválido."
            )

        provider = provider.strip().lower()

        if provider in [
            "auto",
            "vany-auto"
        ]:

            self.provider = "auto"
            self.model = "vany-auto"

            return self.info()

        if provider in [
            "local",
            "vany-local"
        ]:

            self.provider = "local"
            self.model = "local"

            return self.info()

        if provider in [
            "gemini",
            "vany-fast"
        ]:

            self.provider = "gemini"

            if model not in [
                None,
                "",
                "auto",
                "vany-fast"
            ]:

                self.gemini.model = model

            self.model = self.gemini.model

            return self.info()

        if provider in [
            "openrouter",
            "vany-pro"
        ]:

            self.provider = "openrouter"

            if model not in [
                None,
                "",
                "auto",
                "vany-pro"
            ]:

                self.openrouter.model = model

            self.model = self.openrouter.model

            return self.info()

        if provider in [
            "openai",
            "vany-openai"
        ]:

            self.provider = "openai"

            if model not in [
                None,
                "",
                "auto",
                "vany-openai"
            ]:

                self.openai.model = model

            self.model = self.openai.model

            return self.info()

        if provider in [
            "claude",
            "anthropic",
            "vany-claude"
        ]:

            self.provider = "claude"

            if model not in [
                None,
                "",
                "auto",
                "vany-claude"
            ]:

                self.claude.model = model

            self.model = self.claude.model

            return self.info()

        if provider in [
            "deepseek",
            "vany-deepseek"
        ]:

            self.provider = "deepseek"

            if model not in [
                None,
                "",
                "auto",
                "vany-deepseek"
            ]:

                self.deepseek.model = model

            self.model = self.deepseek.model

            return self.info()

        raise ValueError(
            "Provider não suportado: "
            + provider
        )

    # ========================================================
    # PROVIDER OBJECT
    # ========================================================

    def _get_provider(
        self,
        nome
    ):

        if nome == "gemini":
            return self.gemini

        if nome == "openrouter":
            return self.openrouter

        if nome == "openai":
            return self.openai

        if nome == "claude":
            return self.claude

        if nome == "deepseek":
            return self.deepseek

        return None

    # ========================================================
    # RESPOSTA MANUAL
    # ========================================================

    def responder_manual(
        self,
        prompt,
        image=None,
        images=None
    ):

        provider = self._get_provider(
            self.provider
        )

        if provider is None:

            raise RuntimeError(
                "Provider não suporta resposta online."
            )

        if not provider.configurado():

            raise RuntimeError(
                "Provider "
                + self.provider
                + " não está configurado."
            )

        # ----------------------------------------------------
        # Compatibilidade com providers antigos
        # ----------------------------------------------------

        if images:

            try:

                resposta = provider.responder(
                    prompt,
                    image=image,
                    images=images
                )

            except TypeError:

                resposta = provider.responder(
                    prompt,
                    image=image
                )

        else:

            resposta = provider.responder(
                prompt,
                image=image
            )

        return {

            "success": True,

            "provider":
                self.provider,

            "model":
                provider.model,

            "response":
                resposta,

            "fallback":
                False,

            "local_fallback":
                False,

            "errors":
                []
        }

    # ========================================================
    # AUTO ROUTER
    # ========================================================

    def responder_auto(
        self,
        prompt,
        image=None,
        images=None
    ):

        erros = []

        # ====================================================
        # TENTAR PROVIDERS ONLINE NA ORDEM
        # ====================================================

        for nome in self.fallback_order:

            # ------------------------------------------------
            # MODELO LOCAL
            # ------------------------------------------------

            if nome == "local":

                try:

                    engine = VanyEngineV05()

                    mensagem_local = str(
                        prompt
                    )

                    resposta_local = engine.responder(
                        mensagem_local
                    )

                    if resposta_local is None:

                        raise RuntimeError(
                            "Modelo local retornou resposta vazia."
                        )

                    resposta_local = str(
                        resposta_local
                    ).strip()

                    if not resposta_local:

                        raise RuntimeError(
                            "Modelo local retornou resposta vazia."
                        )

                    print(
                        "Router: fallback local OK"
                    )

                    return {

                        "success":
                            True,

                        "provider":
                            "local",

                        "model":
                            "local",

                        "response":
                            resposta_local,

                        "fallback":
                            True,

                        "local_fallback":
                            True,

                        "errors":
                            erros
                    }

                except Exception as erro:

                    print(
                        "Router: fallback local falhou:"
                    )

                    print(
                        repr(erro)
                    )

                    erros.append({

                        "provider":
                            "local",

                        "error":
                            str(erro)
                    })

                    break

            # ------------------------------------------------
            # OBTER PROVIDER
            # ------------------------------------------------

            provider = self._get_provider(
                nome
            )

            if provider is None:

                erros.append({

                    "provider":
                        nome,

                    "error":
                        "Provider não encontrado."
                })

                continue

            # ------------------------------------------------
            # VERIFICAR CONFIGURAÇÃO
            # ------------------------------------------------

            try:

                configurado = provider.configurado()

            except Exception as erro:

                configurado = False

                erros.append({

                    "provider":
                        nome,

                    "error":
                        "Erro ao verificar configuração: "
                        + str(erro)
                })

            if not configurado:

                erros.append({

                    "provider":
                        nome,

                    "error":
                        "Provider não configurado."
                })

                continue

            # ------------------------------------------------
            # TENTAR PROVIDER ONLINE
            # ------------------------------------------------

            try:

                print(
                    "Router: tentando provider "
                    + nome
                )

                if images:

                    try:

                        resposta = provider.responder(
                            prompt,
                            image=image,
                            images=images
                        )

                    except TypeError:

                        resposta = provider.responder(
                            prompt,
                            image=image
                        )

                else:

                    resposta = provider.responder(
                        prompt,
                        image=image
                    )

                if resposta is None:

                    raise RuntimeError(
                        "Provider retornou resposta vazia."
                    )

                resposta = str(
                    resposta
                ).strip()

                if not resposta:

                    raise RuntimeError(
                        "Provider retornou resposta vazia."
                    )

                print(
                    "Router: provider "
                    + nome
                    + " respondeu OK"
                )

                return {

                    "success":
                        True,

                    "provider":
                        nome,

                    "model":
                        provider.model,

                    "response":
                        resposta,

                    "fallback":
                        len(erros) > 0,

                    "local_fallback":
                        False,

                    "errors":
                        erros
                }

            except Exception as erro:

                print(
                    "Router: provider "
                    + nome
                    + " falhou:"
                )

                print(
                    repr(erro)
                )

                erros.append({

                    "provider":
                        nome,

                    "error":
                        str(erro)
                })

                continue

        # ====================================================
        # NENHUM PROVIDER CONSEGUIU RESPONDER
        # ====================================================

        return {

            "success":
                False,

            "provider":
                "none",

            "model":
                None,

            "response":
                None,

            "fallback":
                True,

            "local_fallback":
                True,

            "errors":
                erros
        }

    # ========================================================
    # RESPOSTA PRINCIPAL
    # ========================================================

    def responder(
        self,
        prompt,
        image=None,
        images=None
    ):

        if self.provider == "auto":

            return self.responder_auto(
                prompt,
                image=image,
                images=images
            )

        return self.responder_manual(
            prompt,
            image=image,
            images=images
        )

    # ========================================================
    # TRANSCRIÇÃO DE ÁUDIO
    # ========================================================

    def transcrever_audio(
        self,
        audio_base64,
        formato="m4a"
    ):

        provider = self._get_provider(
            self.provider
        )

        if provider is None:

            raise RuntimeError(
                "Provider atual não suporta STT."
            )

        if not hasattr(
            provider,
            "transcrever_audio"
        ):

            raise RuntimeError(
                "Provider "
                + self.provider
                + " não suporta transcrição de áudio."
            )

        if not provider.configurado():

            raise RuntimeError(
                "Provider "
                + self.provider
                + " não está configurado."
            )

        return provider.transcrever_audio(
            audio_base64,
            formato
        )

    # ========================================================
    # TEXTO PARA VOZ
    # ========================================================

    def gerar_voz(
        self,
        texto
    ):

        provider = self._get_provider(
            self.provider
        )

        if provider is None:

            raise RuntimeError(
                "Provider atual não suporta TTS."
            )

        if not hasattr(
            provider,
            "gerar_voz"
        ):

            raise RuntimeError(
                "Provider "
                + self.provider
                + " não suporta geração de voz."
            )

        if not provider.configurado():

            raise RuntimeError(
                "Provider "
                + self.provider
                + " não está configurado."
            )

        return provider.gerar_voz(
            texto
        )
