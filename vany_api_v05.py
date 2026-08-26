#!/usr/bin/env python3
import os
# -*- coding: utf-8 -*-

# ============================================================
# VANY IA - API V05.6
# ============================================================
# Recursos:
# - Modelo local
# - Gemini
# - OpenRouter
# - Seleção de provider
# - Conversas por conversation_id
# - Histórico enviado ao provider online
# - Fallback automático para modelo local
# - Health / Info / Provider
# - Limpeza de conversa
# ============================================================

from flask import Flask, request, jsonify

from engine_v05 import VanyEngineV05
from provider_v05 import ProviderManager

import uuid
import threading


# ============================================================
# CONFIGURAÇÃO
# ============================================================

app = Flask(__name__)

ENGINE_VERSION = "05.6"

MAX_CONVERSATIONS = 100

HISTORY_FOR_ONLINE = 10


# ============================================================
# PROVIDER
# ============================================================

provider_manager = ProviderManager()


# ============================================================
# CONVERSAS
# ============================================================

conversas = {}

lock = threading.Lock()


def criar_conversa():

    conversation_id = str(
        uuid.uuid4()
    )

    with lock:

        if len(conversas) >= MAX_CONVERSATIONS:

            primeiro = next(
                iter(conversas)
            )

            del conversas[primeiro]

        conversas[conversation_id] = (
            VanyEngineV05()
        )

    return conversation_id


def obter_conversa(
    conversation_id
):

    if not conversation_id:
        return None

    with lock:

        return conversas.get(
            conversation_id
        )


# ============================================================
# PROVIDER INFO
# ============================================================

def obter_provider():

    try:

        return provider_manager.info()

    except Exception as erro:

        print(
            "Erro ao obter provider:",
            erro
        )

        return {

            "provider":
                "local",

            "model":
                "local",

            "configured":
                True
        }


# ============================================================
# HISTÓRICO PARA PROVIDER ONLINE
# ============================================================

def construir_prompt_online(
    mensagem,
    conversation_id
):

    partes = []


    engine_conversa = obter_conversa(
        conversation_id
    )


    if engine_conversa is not None:

        historico = getattr(
            engine_conversa.historico,
            "mensagens",
            []
        )


        for item in historico[
            -HISTORY_FOR_ONLINE:
        ]:

            role = item.get(
                "role",
                ""
            )

            content = item.get(
                "content",
                ""
            )


            if not content:
                continue


            if role == "user":

                partes.append(
                    "Usuário: "
                    + str(content)
                )


            elif role == "assistant":

                partes.append(
                    "Vany: "
                    + str(content)
                )


    # ========================================================
    # PROMPT
    # ========================================================

    if partes:

        prompt = (
            "Você é a Vany IA, uma assistente "
            "de inteligência artificial. "
            "Responda naturalmente em português. "
            "Use o histórico abaixo para manter "
            "o contexto da conversa. "
            "Quando o usuário informar seu nome "
            "ou outra informação durante a conversa, "
            "use essa informação quando ela for "
            "necessária para responder.\n\n"

            "HISTÓRICO DA CONVERSA:\n"

            + "\n".join(partes)

            + "\n\n"

            "MENSAGEM ATUAL DO USUÁRIO:\n"

            + mensagem

            + "\n\n"

            "Vany:"
        )

    else:

        prompt = (
            "Você é a Vany IA, uma assistente "
            "de inteligência artificial. "
            "Responda naturalmente em português.\n\n"
            "Usuário: "
            + mensagem
            + "\nVany:"
        )


    return prompt


# ============================================================
# PROVIDER ONLINE
# ============================================================

def responder_online(
    mensagem,
    conversation_id=None
):

    try:

        provider_info = (
            provider_manager.info()
        )


        provider_nome = provider_info.get(
            "provider",
            "local"
        )


        if provider_nome == "local":

            return None


        # ====================================================
        # CONSTRUIR PROMPT COM HISTÓRICO
        # ====================================================

        prompt = construir_prompt_online(
            mensagem,
            conversation_id
        )


        # ====================================================
        # ENVIAR AO PROVIDER
        # ====================================================

        resposta = (
            provider_manager.responder(
                prompt
            )
        )


        if resposta is None:

            return None


        if not isinstance(
            resposta,
            str
        ):

            resposta = str(
                resposta
            )


        resposta = resposta.strip()


        if not resposta:

            return None


        return resposta


    except Exception as erro:

        print(
            "Provider online indisponível:",
            erro
        )

        return None


# ============================================================
# MODELO LOCAL
# ============================================================

def responder_local(
    mensagem,
    conversation_id=None
):

    engine = None


    if conversation_id:

        engine = obter_conversa(
            conversation_id
        )


    if engine is None:

        engine = VanyEngineV05()


    try:

        resposta = engine.responder(
            mensagem
        )

        return resposta


    except Exception as erro:

        print(
            "Erro no modelo local:",
            erro
        )

        return (
            "Desculpe, ocorreu um erro "
            "no modelo local."
        )


# ============================================================
# ROTA PRINCIPAL
# ============================================================

@app.get("/")
def inicio():

    return jsonify({

        "success":
            True,

        "name":
            "Vany IA",

        "engine":
            ENGINE_VERSION,

        "status":
            "online",

        "api":
            "Vany API"
    })


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():

    provider = obter_provider()


    return jsonify({

        "success":
            True,

        "status":
            "ok",

        "engine":
            ENGINE_VERSION,

        "provider":
            provider.get(
                "provider",
                "local"
            ),

        "conversations":
            len(conversas)
    })


# ============================================================
# INFO
# ============================================================

@app.get("/info")
def info():

    provider = obter_provider()


    return jsonify({

        "success":
            True,

        "name":
            "Vany IA",

        "engine":
            ENGINE_VERSION,

        "mode":
            provider.get(
                "provider",
                "local"
            ),

        "model":
            "vany_model_v04.json",

        "provider":
            provider.get(
                "provider",
                "local"
            ),

        "provider_model":
            provider.get(
                "model",
                "local"
            ),

        "provider_configured":
            provider.get(
                "configured",
                False
            ),

        "conversations":
            len(conversas)
    })


# ============================================================
# PROVIDER
# ============================================================

@app.get("/provider")
def provider():

    info_provider = obter_provider()


    return jsonify({

        "success":
            True,

        "engine":
            ENGINE_VERSION,

        "provider":
            info_provider.get(
                "provider",
                "local"
            ),

        "model":
            info_provider.get(
                "model",
                "local"
            ),

        "configured":
            info_provider.get(
                "configured",
                False
            )
    })


# ============================================================
# SELECIONAR PROVIDER
# ============================================================

@app.post("/provider/select")
def selecionar_provider():

    try:

        dados = request.get_json(
            silent=True
        )


        if not isinstance(
            dados,
            dict
        ):

            return jsonify({

                "success":
                    False,

                "error":
                    "JSON inválido."
            }), 400


        provider = dados.get(
            "provider",
            ""
        )


        model = dados.get(
            "model",
            "auto"
        )


        if not isinstance(
            provider,
            str
        ):

            return jsonify({

                "success":
                    False,

                "error":
                    "provider deve ser texto."
            }), 400


        resultado = (
            provider_manager.selecionar(
                provider,
                model
            )
        )


        return jsonify({

            "success":
                True,

            "engine":
                ENGINE_VERSION,

            "provider":
                resultado.get(
                    "provider",
                    provider
                ),

            "model":
                resultado.get(
                    "model",
                    model
                ),

            "configured":
                resultado.get(
                    "configured",
                    False
                )
        })


    except Exception as erro:

        print(
            "ERRO /provider/select:",
            erro
        )


        return jsonify({

            "success":
                False,

            "engine":
                ENGINE_VERSION,

            "error":
                str(erro)

        }), 400


# ============================================================
# CHAT
# ============================================================

@app.post("/chat")
def chat():

    try:

        dados = request.get_json(
            silent=True
        )


        if not isinstance(
            dados,
            dict
        ):

            return jsonify({

                "success":
                    False,

                "error":
                    "JSON inválido."
            }), 400


        mensagem = dados.get(
            "message",
            ""
        )


        if not isinstance(
            mensagem,
            str
        ):

            return jsonify({

                "success":
                    False,

                "error":
                    "message deve ser texto."
            }), 400


        mensagem = mensagem.strip()


        if not mensagem:

            return jsonify({

                "success":
                    False,

                "error":
                    "Mensagem vazia."
            }), 400


        # ====================================================
        # CONVERSATION ID
        # ====================================================

        conversation_id = dados.get(
            "conversation_id"
        )


        if conversation_id is not None:

            if not isinstance(
                conversation_id,
                str
            ):

                return jsonify({

                    "success":
                        False,

                    "error":
                        "conversation_id deve ser texto."
                }), 400


            if obter_conversa(
                conversation_id
            ) is None:

                return jsonify({

                    "success":
                        False,

                    "error":
                        "conversation_id não encontrado."
                }), 404


        else:

            conversation_id = (
                criar_conversa()
            )


        # ====================================================
        # PROVIDER
        # ====================================================

        provider = obter_provider()


        provider_nome = provider.get(
            "provider",
            "local"
        )


        # ====================================================
        # ONLINE
        #
        # IMPORTANTE:
        # Não adicionamos a mensagem ao histórico
        # antes do prompt online.
        #
        # responder_online() lê o histórico existente
        # e acrescenta a mensagem atual no prompt.
        # ====================================================

        resposta = None


        if provider_nome != "local":

            resposta = responder_online(
                mensagem,
                conversation_id
            )


        # ====================================================
        # FALLBACK LOCAL
        # ====================================================

        if resposta is None:

            resposta = responder_local(
                mensagem,
                conversation_id
            )

            modo = "local"


        else:

            modo = provider_nome


        # ====================================================
        # GUARDAR PERGUNTA + RESPOSTA
        #
        # Somente depois de obter a resposta.
        # Isso evita duplicar a mensagem no prompt online.
        # ====================================================

        engine_conversa = obter_conversa(
            conversation_id
        )


        if engine_conversa is not None:

            engine_conversa.historico.adicionar_usuario(
                mensagem
            )

            engine_conversa.historico.adicionar_vany(
                resposta
            )


        # ====================================================
        # RESPOSTA JSON
        # ====================================================

        return jsonify({

            "success":
                True,

            "engine":
                ENGINE_VERSION,

            "mode":
                modo,

            "provider":
                provider_nome,

            "conversation_id":
                conversation_id,

            "reply":
                resposta
        })


    except Exception as erro:

        print(
            "ERRO /chat:",
            erro
        )


        return jsonify({

            "success":
                False,

            "engine":
                ENGINE_VERSION,

            "error":
                str(erro)

        }), 500


# ============================================================
# LIMPAR CONVERSA
# ============================================================

@app.post("/conversation/clear")
def limpar_conversa():

    try:

        dados = request.get_json(
            silent=True
        )


        if not isinstance(
            dados,
            dict
        ):

            return jsonify({

                "success":
                    False,

                "error":
                    "JSON inválido."
            }), 400


        conversation_id = dados.get(
            "conversation_id"
        )


        if not isinstance(
            conversation_id,
            str
        ):

            return jsonify({

                "success":
                    False,

                "error":
                    "conversation_id deve ser texto."
            }), 400


        with lock:

            if conversation_id in conversas:

                del conversas[
                    conversation_id
                ]


        return jsonify({

            "success":
                True,

            "engine":
                ENGINE_VERSION,

            "conversation_id":
                conversation_id,

            "cleared":
                True
        })


    except Exception as erro:

        print(
            "ERRO /conversation/clear:",
            erro
        )


        return jsonify({

            "success":
                False,

            "engine":
                ENGINE_VERSION,

            "error":
                str(erro)

        }), 500


# ============================================================
# INICIALIZAÇÃO
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("             VANY IA API V05.6")
    print("=" * 60)

    print(
        "Servidor: http://127.0.0.1:5000"
    )

    print(
        "Health:   http://127.0.0.1:5000/health"
    )

    print(
        "Info:     http://127.0.0.1:5000/info"
    )

    print(
        "Provider: GET /provider"
    )

    print(
        "Select:   POST /provider/select"
    )

    print(
        "Chat:     POST /chat"
    )

    print(
        "Clear:    POST /conversation/clear"
    )

    print("=" * 60)


    app.run(
    host="0.0.0.0",
    port=int(os.environ.get("PORT", 5000))
)
