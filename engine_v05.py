#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
VANY IA - ENGINE V05
============================================================

Arquitetura:
    Vany App
       ↓
    Vany API
       ↓
    Engine V05
       ↓
    Modelo local / motor online

Objetivos:
- manter fallback local
- preparar integração com API
- manter histórico de conversa
- separar engine de servidor
- preparar Vany para Sketchware Pro
============================================================
"""

import json
import os
import re
import sys
import unicodedata
from datetime import datetime


# ============================================================
# CONFIGURAÇÃO
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

MODEL_FILE = os.path.join(
    BASE_DIR,
    "vany_model_v04.json"
)

VOCAB_FILE = os.path.join(
    BASE_DIR,
    "vany_vocab.json"
)

ENGINE_VERSION = "05.0"

MAX_HISTORY = 20


# ============================================================
# NORMALIZAÇÃO
# ============================================================

def remover_acentos(texto):

    texto = unicodedata.normalize(
        "NFD",
        texto
    )

    return "".join(
        c
        for c in texto
        if unicodedata.category(c) != "Mn"
    )


def normalizar(texto):

    texto = str(
        texto
    ).lower().strip()

    texto = remover_acentos(
        texto
    )

    substituicoes = {

        "vc": "voce",
        "vcs": "voces",

        "uque": "o que",
        "oque": "o que",

        "pq": "porque",
        "porq": "porque",

        "tb": "tambem",
        "tbm": "tambem",

        "eh": "e",

        "q": "que"
    }

    for antigo, novo in substituicoes.items():

        texto = re.sub(
            rf"\b{re.escape(antigo)}\b",
            novo,
            texto
        )

    texto = re.sub(
        r"\s+",
        " ",
        texto
    )

    return texto.strip()


# ============================================================
# HISTÓRICO
# ============================================================

class Historico:

    def __init__(
        self,
        limite=MAX_HISTORY
    ):

        self.limite = limite

        self.mensagens = []


    def adicionar_usuario(
        self,
        texto
    ):

        self.mensagens.append({

            "role": "user",

            "content": texto,

            "time": datetime.now().isoformat()
        })

        self.limpar_excesso()


    def adicionar_vany(
        self,
        texto
    ):

        self.mensagens.append({

            "role": "assistant",

            "content": texto,

            "time": datetime.now().isoformat()
        })

        self.limpar_excesso()


    def limpar_excesso(self):

        if len(
            self.mensagens
        ) > self.limite:

            self.mensagens = (
                self.mensagens[
                    -self.limite:
                ]
            )


    def limpar(self):

        self.mensagens = []


    def obter(self):

        return list(
            self.mensagens
        )


    def quantidade(self):

        return len(
            self.mensagens
        )


# ============================================================
# MODELO LOCAL
# ============================================================

class ModeloLocal:

    def __init__(self):

        self.modelo = None

        self.carregado = False

        self.carregar()


    def carregar(self):

        try:

            with open(
                MODEL_FILE,
                "r",
                encoding="utf-8"
            ) as arquivo:

                self.modelo = json.load(
                    arquivo
                )

            self.carregado = True

        except Exception as erro:

            print(
                "Aviso: modelo local não carregado:",
                erro
            )

            self.carregado = False


    def info(self):

        if not self.carregado:

            return {

                "loaded": False

            }


        return {

            "loaded": True,

            "version":
                self.modelo.get(
                    "version"
                ),

            "type":
                self.modelo.get(
                    "type"
                ),

            "vocab_size":
                self.modelo.get(
                    "vocab_size"
                ),

            "embedding_dim":
                self.modelo.get(
                    "embedding_dim"
                )
        }


# ============================================================
# VANY ENGINE V05
# ============================================================

class VanyEngineV05:

    def __init__(self):

        self.historico = Historico()

        self.modelo_local = ModeloLocal()

        self.modo = "local"

        self.config = {

            "online": False,

            "provider": None,

            "model": None
        }


    # ========================================================
    # CONFIGURAR MODO
    # ========================================================

    def modo_local(self):

        self.modo = "local"

        self.config["online"] = False

        self.config["provider"] = None

        self.config["model"] = None


    def modo_online(
        self,
        provider,
        model
    ):

        self.modo = "online"

        self.config["online"] = True

        self.config["provider"] = provider

        self.config["model"] = model


    # ========================================================
    # RESPOSTAS BÁSICAS
    # ========================================================

    def resposta_basica(
        self,
        texto
    ):

        p = normalizar(
            texto
        )


        # --------------------------------------------
        # SAUDAÇÃO
        # --------------------------------------------

        if p in [
            "oi",
            "ola",
            "bom dia",
            "boa tarde",
            "boa noite"
        ]:

            return (
                "Olá! 👋 Eu sou a Vany IA. "
                "Como posso ajudar você?"
            )


        # --------------------------------------------
        # IDENTIDADE
        # --------------------------------------------

        if (
            "quem e voce" in p
            or
            "quem e a vany" in p
        ):

            return (
                "Eu sou a Vany IA, uma assistente "
                "de inteligência artificial."
            )


        # --------------------------------------------
        # NOME
        # --------------------------------------------

        if (
            "qual e o seu nome" in p
            or
            "como voce se chama" in p
        ):

            return (
                "Meu nome é Vany IA."
            )


        # --------------------------------------------
        # PYTHON
        # --------------------------------------------

        if "python" in p:

            return (
                "Python é uma linguagem de programação "
                "usada para criar programas, trabalhar "
                "com dados, texto e inteligência artificial."
            )


        # --------------------------------------------
        # IA
        # --------------------------------------------

        if (
            "inteligencia artificial" in p
        ):

            return (
                "Inteligência artificial é uma área da "
                "computação que permite criar sistemas "
                "capazes de analisar informações, aprender "
                "padrões e produzir respostas."
            )


        # --------------------------------------------
        # API
        # --------------------------------------------

        if (
            "o que e api" in p
            or
            "o que e uma api" in p
        ):

            return (
                "Uma API permite que diferentes programas "
                "comuniquem entre si e troquem informações."
            )


        # --------------------------------------------
        # AGRADECIMENTO
        # --------------------------------------------

        if (
            "obrigado" in p
            or
            "obrigada" in p
            or
            "valeu" in p
        ):

            return (
                "De nada! 😊"
            )


        return None


    # ========================================================
    # FALLBACK LOCAL
    # ========================================================

    def responder_local(
        self,
        texto
    ):

        resposta = self.resposta_basica(
            texto
        )

        if resposta:

            return resposta


        if self.modelo_local.carregado:

            return (
                "Recebi sua mensagem. "
                "O modelo local V04 ainda está "
                "em desenvolvimento para esse tipo "
                "de pergunta."
            )


        return (
            "O modo local da Vany está disponível, "
            "mas o modelo não foi carregado."
        )


    # ========================================================
    # RESPOSTA PRINCIPAL
    # ========================================================

    def responder(
        self,
        texto
    ):

        texto = str(
            texto
        ).strip()


        if not texto:

            return (
                "Digite uma mensagem."
            )


        # Guardar pergunta
        self.historico.adicionar_usuario(
            texto
        )


        # --------------------------------------------
        # MODO LOCAL
        # --------------------------------------------

        if self.modo == "local":

            resposta = self.responder_local(
                texto
            )


        # --------------------------------------------
        # MODO ONLINE
        # --------------------------------------------

        else:

            # A integração real com a API será
            # adicionada na próxima etapa.

            resposta = (
                "O modo online da Vany está "
                "preparado, mas a API ainda "
                "não foi conectada."
            )


        # Guardar resposta
        self.historico.adicionar_vany(
            resposta
        )


        return resposta


    # ========================================================
    # INFO
    # ========================================================

    def info(self):

        print()
        print("=" * 60)
        print("          VANY IA - ENGINE V05")
        print("=" * 60)

        print(
            "Engine:",
            ENGINE_VERSION
        )

        print(
            "Modo:",
            self.modo
        )

        print(
            "Modelo local:",
            "SIM"
            if self.modelo_local.carregado
            else "NÃO"
        )

        print(
            "Histórico:",
            self.historico.quantidade(),
            "mensagens"
        )

        print(
            "Online:",
            "SIM"
            if self.config["online"]
            else "NÃO"
        )

        if self.config["provider"]:

            print(
                "Provider:",
                self.config["provider"]
            )

        if self.config["model"]:

            print(
                "Modelo online:",
                self.config["model"]
            )

        print("=" * 60)
        print()


    # ========================================================
    # CHAT
    # ========================================================

    def chat(self):

        print()
        print("=" * 60)
        print("             VANY IA V05")
        print("=" * 60)

        print(
            "Modo atual: LOCAL"
        )

        print(
            "Comandos:"
        )

        print(
            "  sair     - terminar"
        )

        print(
            "  limpar   - limpar histórico"
        )

        print(
            "  info     - informações"
        )

        print("=" * 60)
        print()


        while True:

            try:

                texto = input(
                    "Você: "
                ).strip()

            except (
                KeyboardInterrupt,
                EOFError
            ):

                print()
                print(
                    "Vany: Até logo! 👋"
                )

                break


            if not texto:

                continue


            comando = normalizar(
                texto
            )


            if comando == "sair":

                print()
                print(
                    "Vany: Até logo! 👋"
                )

                break


            if comando == "limpar":

                self.historico.limpar()

                print(
                    "Vany: Histórico limpo."
                )

                continue


            if comando == "info":

                self.info()

                continue


            resposta = self.responder(
                texto
            )

            print(
                "Vany:",
                resposta
            )


# ============================================================
# MAIN
# ============================================================

def main():

    engine = VanyEngineV05()


    if len(
        sys.argv
    ) > 1:

        argumento = sys.argv[1]


        if argumento == "--info":

            engine.info()

            return


        if argumento == "--test":

            perguntas = [

                "Olá",

                "Quem é você?",

                "Quem e vc",

                "Qual é o seu nome?",

                "O que é Python?",

                "O que é inteligência artificial?",

                "O que é uma API?",

                "Obrigado"
            ]


            print()

            for pergunta in perguntas:

                print(
                    "Você:",
                    pergunta
                )

                print(
                    "Vany:",
                    engine.responder(
                        pergunta
                    )
                )

                print()

            return


        pergunta = " ".join(
            sys.argv[1:]
        )

        print(
            "Vany:",
            engine.responder(
                pergunta
            )
        )

        return


    engine.chat()


# ============================================================
# EXECUTAR
# ============================================================

if __name__ == "__main__":

    main()
