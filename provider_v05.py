from openrouter_provider import OpenRouterProvider


class ProviderManager:

    def __init__(self):
        self.provider = OpenRouterProvider()

    def info(self):
        if self.provider is None:
            return {
                "provider": "none",
                "model": "",
                "configured": False
            }

        return self.provider.info()

    def responder(
        self,
        prompt,
        image=None,
        images=None
    ):
        if self.provider is None:
            raise RuntimeError(
                "Provider não configurado"
            )

        return self.provider.responder(
            prompt,
            image=image,
            images=images
        )

    def transcrever_audio(
        self,
        audio_base64,
        formato="m4a"
    ):
        if self.provider is None:
            raise RuntimeError(
                "Provider não configurado"
            )

        if not hasattr(
            self.provider,
            "transcrever_audio"
        ):
            raise RuntimeError(
                "Provider atual não suporta transcrição de áudio"
            )

        return self.provider.transcrever_audio(
            audio_base64,
            formato
        )

    def gerar_voz(
        self,
        texto
    ):
        if self.provider is None:
            raise RuntimeError(
                "Provider não configurado"
            )

        if not hasattr(
            self.provider,
            "gerar_voz"
        ):
            raise RuntimeError(
                "Provider atual não suporta voz"
            )

        return self.provider.gerar_voz(
            texto
        )
