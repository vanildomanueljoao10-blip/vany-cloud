#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
VANY IA - ENGINE V05.1
============================================================

Motor local da Vany IA.

Recursos:
- respostas básicas
- matemática simples
- identidade da Vany
- explicações educativas
- histórico local
- carregamento do modelo V04
- fallback seguro
============================================================
"""

import json
import os
import re
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

ENGINE_VERSION = "05.1"

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

    texto = str(texto).lower().strip()

    texto = remover_acentos(texto)

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


    def adicionar_usuario(self, texto):

        self.mensagens.append({
            "role": "user",
            "content": texto,
            "time": datetime.now().isoformat()
        })

        self.limpar_excesso()


    def adicionar_vany(self, texto):

        self.mensagens.append({
            "role": "assistant",
            "content": texto,
            "time": datetime.now().isoformat()
        })

        self.limpar_excesso()


    def limpar_excesso(self):

        if len(self.mensagens) > self.limite:

            self.mensagens = (
                self.mensagens[-self.limite:]
            )


    def limpar(self):

        self.mensagens = []


    def obter(self):

        return list(self.mensagens)


    def quantidade(self):

        return len(self.mensagens)


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
            "version": self.modelo.get("version"),
            "type": self.modelo.get("type"),
            "vocab_size": self.modelo.get("vocab_size"),
            "embedding_dim": self.modelo.get("embedding_dim")
        }


# ============================================================
# MOTOR VANY V05.1
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
    # MODO
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
    # MATEMÁTICA
    # ========================================================

    def calcular(self, texto):
        texto = texto.strip().lower()

        # Remove acentos para facilitar o reconhecimento.
        import unicodedata
        # Preserva símbolos matemáticos antes de remover acentos.
        texto = texto.replace("÷", "__DIVISAO__")

        texto = unicodedata.normalize(
            "NFD",
            texto
        ).encode(
            "ascii",
            "ignore"
        ).decode("ascii")

        texto = texto.replace("__DIVISAO__", "÷")

        expressao = None

        prefixos = [
            "quanto e ",
            "quanto da ",
            "calcule ",
            "calcular ",
            "resultado de "
        ]

        for prefixo in prefixos:
            if texto.startswith(prefixo):
                expressao = texto[len(prefixo):].strip()
                break

        if expressao is None:
            return None

        # Remove pontuação no final.
        expressao = re.sub(
            r"[?!.,;:]+$",
            "",
            expressao
        ).strip()

        # Converte símbolos matemáticos.
        expressao = expressao.replace("x", "*")
        expressao = expressao.replace("÷", "/")

        # Aceita somente matemática simples.
        if not re.fullmatch(
            r"[0-9+\-*/(). ]+",
            expressao
        ):
            return None

        try:
            resultado = eval(
                expressao,
                {"__builtins__": {}},
                {}
            )

            if isinstance(resultado, float):
                if resultado.is_integer():
                    resultado = int(resultado)
                else:
                    resultado = round(resultado, 10)

            return f"O resultado é {resultado}."

        except Exception:
            return None

    def resposta_basica(
        self,
        texto
    ):

        p = normalizar(texto)


        # SAUDAÇÕES
        if p in [
            "oi",
            "ola",
            "ola vany",
            "oi vany",
            "bom dia",
            "boa tarde",
            "boa noite"
        ]:

            return (
                "Olá! 👋 Eu sou a Vany IA. "
                "Como posso ajudar você?"
            )


        # IDENTIDADE
        if (
            "quem e voce" in p
            or
            "quem e a vany" in p
            or
            "quem es tu" in p
            or
            "quem es voce" in p
        ):

            return (
                "Eu sou a Vany IA, uma assistente "
                "de inteligência artificial criada "
                "para ajudar com perguntas, estudos, "
                "programação e informações."
            )


        # NOME
        if (
            "qual e o seu nome" in p
            or
            "como voce se chama" in p
            or
            "seu nome" in p
        ):

            return "Meu nome é Vany IA."


        # CRIADOR / PROJETO
        if (
            "o que e a vany" in p
            or
            "sobre a vany" in p
        ):

            return (
                "A Vany IA é um projeto de assistente "
                "de inteligência artificial com motor "
                "local e integração com diferentes "
                "provedores de IA."
            )


        # PYTHON
        if "python" in p:

            return (
                "Python é uma linguagem de programação "
                "de alto nível usada em aplicações, "
                "automação, dados, inteligência artificial "
                "e desenvolvimento de software."
            )


        # IA
        if (
            "inteligencia artificial" in p
            or
            "o que e ia" in p
        ):

            return (
                "Inteligência artificial é uma área da "
                "computação que desenvolve sistemas "
                "capazes de processar informações, "
                "identificar padrões e realizar tarefas "
                "que normalmente exigem inteligência humana."
            )


        # API
        if (
            "o que e api" in p
            or
            "o que e uma api" in p
        ):

            return (
                "Uma API é uma interface que permite "
                "que diferentes programas comuniquem "
                "entre si e troquem dados ou serviços."
            )


        # ROUTER
        if (
            "router" in p
            or
            "roteador" in p
        ):

            return (
                "O Vany Router é o sistema que seleciona "
                "entre diferentes provedores de IA e pode "
                "usar o modelo local da Vany quando os "
                "serviços online não estão disponíveis."
            )


        # FALLBACK
        if (
            "fallback" in p
        ):

            return (
                "Fallback é uma estratégia de segurança "
                "na qual a Vany tenta outra opção quando "
                "o serviço principal falha."
            )


        # OBRIGADO
        if (
            "obrigado" in p
            or
            "obrigada" in p
            or
            "valeu" in p
        ):

            return "De nada! 😊"


        # COMO ESTÁ
        if (
            "tudo bem" in p
            or
            "como voce esta" in p
        ):

            return (
                "Estou funcionando e pronta para ajudar! 😊"
            )


        # ESTUDOS
        if (
            "ajuda nos estudos" in p
            or
            "podes me ajudar" in p
            or
            "pode me ajudar" in p
        ):

            return (
                "Claro! 📚 Posso ajudar a explicar "
                "matérias, resolver exercícios e "
                "organizar seus estudos."
            )


        return None


    # ========================================================
    # FALLBACK LOCAL
    # ========================================================

    def responder_local(
        self,
        texto
    ):

        resposta = self.calcular(
            texto
        )

        if resposta:

            return resposta


        resposta = self.resposta_basica(
            texto
        )

        if resposta:

            return resposta


        if self.modelo_local.carregado:

            return (
                "Ainda estou aprendendo essa pergunta "
                "no modo local. Posso ajudar melhor com "
                "matemática simples, programação, IA, "
                "APIs e perguntas básicas."
            )


        return (
            "O modo local da Vany está disponível, "
            "mas o modelo local não foi carregado."
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

            return "Digite uma mensagem."


        self.historico.adicionar_usuario(
            texto
        )


        if self.modo == "local":

            resposta = self.responder_local(
                texto
            )

        else:

            resposta = (
                "O modo online está preparado "
                "para ser utilizado pelo Vany Router."
            )


        self.historico.adicionar_vany(
            resposta
        )

        return resposta


    # ========================================================
    # INFO
    # ========================================================

    def info(self):

        dados = {
            "engine": ENGINE_VERSION,
            "mode": self.modo,
            "local_model": self.modelo_local.info(),
            "history": self.historico.quantidade(),
            "online": self.config["online"],
            "provider": self.config["provider"],
            "model": self.config["model"]
        }

        print()
        print("=" * 60)
        print("          VANY IA - ENGINE V05.1")
        print("=" * 60)
        print("Engine:", ENGINE_VERSION)
        print("Modo:", self.modo)
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
        print("=" * 60)
        print()

        return dados


# ============================================================
# EXECUÇÃO DIRETA
# ============================================================

if __name__ == "__main__":

    engine = VanyEngineV05()

    engine.info()

    print("Digite 'sair' para terminar.")
    print()

    while True:

        try:

            pergunta = input("Você: ").strip()

        except (
            KeyboardInterrupt,
            EOFError
        ):

            print("\nVany: Até logo! 👋")
            break

        if not pergunta:

            continue

        if normalizar(pergunta) == "sair":

            print("Vany: Até logo! 👋")
            break

        resposta = engine.responder(
            pergunta
        )

        print(
            "Vany:",
            resposta
        )
