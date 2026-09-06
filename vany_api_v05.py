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
from key_manager_v12 import verificar_api_key as verificar_api_key_db
from usage_manager_v14 import registrar_usage, inicializar_usage

import uuid
import threading
import time


# ============================================================
# CONFIGURAÇÃO
# ============================================================

app = Flask(__name__)

ENGINE_VERSION = "05.6"

MAX_CONVERSATIONS = 100

HISTORY_FOR_ONLINE = 10


# ============================================================
# VANY API V1.1 - AUTENTICAÇÃO
# ============================================================

VANY_API_KEY = os.environ.get("VANY_API_KEY", "").strip()


def verificar_api_key():

    autorizacao = request.headers.get(
        "Authorization",
        ""
    ).strip()

    if not autorizacao.startswith("Bearer "):

        return False

    chave = autorizacao[7:].strip()

    if not chave:

        return False

    # Primeiro: chaves gerenciadas pelo Vany Key Manager
    if verificar_api_key_db(chave):

        return True

    # Compatibilidade temporária com VANY_API_KEY
    return bool(
        VANY_API_KEY
        and chave == VANY_API_KEY
    )


def erro_auth():

    return jsonify({

        "error": {

            "type":
                "authentication_error",

            "message":
                "API key inválida ou ausente."

        }

    }), 401


# ============================================================
# VANY API V1.4 - USAGE TRACKING
# ============================================================

def obter_api_key_id(api_key):

    if not api_key:
        return None

    import hashlib
    import sqlite3
    from pathlib import Path

    key_hash = hashlib.sha256(
        api_key.encode("utf-8")
    ).hexdigest()

    db_path = Path("vany_keys.db")

    with sqlite3.connect(db_path) as db:
        db.execute("PRAGMA foreign_keys = ON")

        row = db.execute(
            """
            SELECT id
            FROM api_keys
            WHERE key_hash = ?
            LIMIT 1
            """,
            (key_hash,)
        ).fetchone()

    if row is None:
        return None

    return row[0]


def registrar_uso_api(
    endpoint,
    model,
    status_code
):

    api_key = obter_chave_autorizacao()

    if not api_key:
        return

    api_key_id = obter_api_key_id(api_key)

    if api_key_id is None:
        return

    registrar_usage(
        api_key_id,
        endpoint,
        model,
        status_code
    )


# ============================================================
# VANY API V1.3 - RATE LIMITING
# ============================================================

RATE_LIMIT_REQUESTS = 20
RATE_LIMIT_WINDOW = 60

rate_limit_data = {}
rate_limit_lock = threading.Lock()


def obter_chave_autorizacao():

    autorizacao = request.headers.get(
        "Authorization",
        ""
    ).strip()

    if not autorizacao.startswith("Bearer "):

        return ""

    return autorizacao[7:].strip()


def verificar_rate_limit():

    chave = obter_chave_autorizacao()

    if not chave:

        return False

    agora = time.time()

    with rate_limit_lock:

        registros = rate_limit_data.get(
            chave,
            []
        )

        registros = [
            timestamp
            for timestamp in registros
            if agora - timestamp < RATE_LIMIT_WINDOW
        ]

        if len(registros) >= RATE_LIMIT_REQUESTS:

            rate_limit_data[chave] = registros

            return False

        registros.append(agora)

        rate_limit_data[chave] = registros

    return True


def erro_rate_limit():

    return jsonify({

        "error": {

            "type":
                "rate_limit_error",

            "message":
                "Limite de requisições excedido. Tente novamente mais tarde."

        }

    }), 429




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
        # RESPOSTA
        # ====================================================

        resposta = None


        # ====================================================
        # IDENTIDADE DA VANY
        # ====================================================

        mensagem_identidade = (
            mensagem.lower().strip()
        )


        # NOME
        if (
            "qual é o seu nome" in mensagem_identidade
            or
            "qual e o seu nome" in mensagem_identidade
            or
            "como você se chama" in mensagem_identidade
            or
            "como voce se chama" in mensagem_identidade
            or
            "quem é você" in mensagem_identidade
            or
            "quem e voce" in mensagem_identidade
        ):

            resposta = (
                "Meu nome é Vany."
            )


        # CRIADOR
        elif (
            "quem é o seu criador" in mensagem_identidade
            or
            "quem e o seu criador" in mensagem_identidade
            or
            "quem criou você" in mensagem_identidade
            or
            "quem criou voce" in mensagem_identidade
            or
            "quem fez você" in mensagem_identidade
            or
            "quem fez voce" in mensagem_identidade
        ):

            resposta = (
                "Meu criador é Vanildo."
            )


        # LOCAL DE CRIAÇÃO
        elif (
            "onde foste criada" in mensagem_identidade
            or
            "onde foi criada" in mensagem_identidade
            or
            "onde você foi criada" in mensagem_identidade
            or
            "onde voce foi criada" in mensagem_identidade
            or
            "onde você nasceu" in mensagem_identidade
            or
            "onde voce nasceu" in mensagem_identidade
        ):

            resposta = (
                "Fui criada em Moçambique."
            )


        # ====================================================
        # ONLINE
        # ====================================================

        if (
            resposta is None
            and
            provider_nome != "local"
        ):

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

            if (
                provider_nome != "local"
                and
                resposta is not None
            ):

                modo = provider_nome

            else:

                modo = "local"


        # ====================================================
        # GARANTIR RESPOSTA TEXTO
        # ====================================================

        if resposta is None:

            resposta = (
                "Desculpe, não consegui gerar uma resposta."
            )


        resposta = str(
            resposta
        )


        # ====================================================
        # GUARDAR PERGUNTA + RESPOSTA
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

            "error":
                str(erro)

        }), 500
# ============================================================
# VANY API V1
# ============================================================

@app.get("/v1/health")
def v1_health():

    return jsonify({

        "status":
            "ok",

        "service":
            "Vany API",

        "version":
            "1.0.0",

        "engine":
            ENGINE_VERSION

    })


@app.get("/v1/models")
def v1_models():

    if not verificar_api_key():

        return erro_auth()

    if not verificar_rate_limit():

        return erro_rate_limit()

    registrar_uso_api(
        "/v1/models",
        None,
        200
    )

    return jsonify({

        "object":
            "list",

        "data": [

            {
                "id":
                    "vany-fast",

                "object":
                    "model",

                "provider":
                    "vany",

                "capabilities": [
                    "text"
                ]
            },

            {
                "id":
                    "vany-pro",

                "object":
                    "model",

                "provider":
                    "vany",

                "capabilities": [
                    "text"
                ]
            }

        ]

    })


@app.post("/v1/chat")
def v1_chat():

    if not verificar_api_key():

        return erro_auth()

    if not verificar_rate_limit():

        return erro_rate_limit()

    try:

        dados = request.get_json(
            silent=True
        )

        if not isinstance(
            dados,
            dict
        ):

            return jsonify({

                "error": {

                    "type":
                        "invalid_request",

                    "message":
                        "JSON inválido."

                }

            }), 400


        model = dados.get(
            "model",
            "vany-fast"
        )


        messages = dados.get(
            "messages"
        )


        if not isinstance(
            messages,
            list
        ):

            return jsonify({

                "error": {

                    "type":
                        "invalid_request",

                    "message":
                        "messages deve ser uma lista."

                }

            }), 400


        if len(messages) == 0:

            return jsonify({

                "error": {

                    "type":
                        "invalid_request",

                    "message":
                        "messages não pode estar vazio."

                }

            }), 400


        ultima_mensagem = messages[-1]


        if not isinstance(
            ultima_mensagem,
            dict
        ):

            return jsonify({

                "error": {

                    "type":
                        "invalid_request",

                    "message":
                        "Mensagem inválida."

                }

            }), 400


        mensagem = ultima_mensagem.get(
            "content",
            ""
        )


        if not isinstance(
            mensagem,
            str
        ):

            return jsonify({

                "error": {

                    "type":
                        "invalid_request",

                    "message":
                        "content deve ser texto."

                }

            }), 400


        mensagem = mensagem.strip()


        if not mensagem:

            return jsonify({

                "error": {

                    "type":
                        "invalid_request",

                    "message":
                        "content não pode estar vazio."

                }

            }), 400


        # ----------------------------------------------------
        # REUTILIZAR O MOTOR EXISTENTE
        # ----------------------------------------------------

        with app.test_request_context(
            "/chat",
            method="POST",
            json={
                "message": mensagem
            }
        ):

            resposta = chat()


        # ----------------------------------------------------
        # CONVERTER RESPOSTA DO FLASK
        # ----------------------------------------------------

        if isinstance(
            resposta,
            tuple
        ):

            response_object = resposta[0]
            status_code = resposta[1]

        else:

            response_object = resposta
            status_code = 200


        dados_resposta = response_object.get_json()


        if status_code != 200:

            registrar_uso_api(
                "/v1/chat",
                model,
                status_code
            )

            return jsonify({

                "error": {

                    "type":
                        "engine_error",

                    "message":
                        dados_resposta.get(
                            "error",
                            "Erro ao processar pedido."
                        )

                }

            }), status_code


        reply = dados_resposta.get(
            "reply",
            ""
        )


        registrar_uso_api(
            "/v1/chat",
            model,
            200
        )


        return jsonify({

            "id":
                "vny_chat",

            "object":
                "chat.completion",

            "model":
                model,

            "provider":
                "vany",

            "choices": [

                {

                    "index":
                        0,

                    "message": {

                        "role":
                            "assistant",

                        "content":
                            reply

                    },

                    "finish_reason":
                        "stop"

                }

            ]

        })


    except Exception as erro:

        print(
            "ERRO /v1/chat:",
            erro
        )


        return jsonify({

            "error": {

                "type":
                    "server_error",

                "message":
                    str(erro)

            }

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
