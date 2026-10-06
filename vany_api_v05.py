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

from flask import Flask, request, jsonify, redirect, session

from authlib.integrations.flask_client import OAuth
import sqlite3
import secrets

from engine_v05 import VanyEngineV05
from provider_v06 import ProviderManager
from key_manager_v12 import verificar_api_key as verificar_api_key_db
from usage_manager_v14 import registrar_usage, inicializar_usage
from premium_manager import premium_manager
from premium_access import get_premium_access

import uuid
import threading
import time


# ============================================================
# CONFIGURAÇÃO
# ============================================================

app = Flask(__name__)

# ============================================================
# VANY IA — GOOGLE OAUTH
# ============================================================

app.secret_key = os.environ.get(
    "VANY_FLASK_SECRET",
    ""
).strip()

if not app.secret_key:
    raise RuntimeError(
        "VANY_FLASK_SECRET não configurado."
    )

oauth = OAuth(app)

google = oauth.register(
    name="google",

    client_id=os.environ.get(
        "GOOGLE_CLIENT_ID",
        ""
    ).strip(),

    client_secret=os.environ.get(
        "GOOGLE_CLIENT_SECRET",
        ""
    ).strip(),

    server_metadata_url=
        "https://accounts.google.com/.well-known/openid-configuration",

    client_kwargs={
        "scope": "openid email profile"
    }
)

GOOGLE_REDIRECT_URI = os.environ.get(
    "GOOGLE_REDIRECT_URI",
    "https://vany-cloud.onrender.com/auth/google/callback"
).strip()

GOOGLE_AUTH_DATABASE = "vany_google_auth.db"


def inicializar_google_auth():

    with sqlite3.connect(
        GOOGLE_AUTH_DATABASE
    ) as db:

        db.execute("""
            CREATE TABLE IF NOT EXISTS google_users (
                google_sub TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                email TEXT,
                name TEXT,
                picture TEXT,
                created_at TEXT NOT NULL
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS google_codes (
                code TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at REAL NOT NULL,
                used INTEGER DEFAULT 0
            )
        """)

        db.commit()


inicializar_google_auth()

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
    conversation_id=None,
    image=None,
    images=None
):

    provider = provider_manager.info()

    provider_nome = provider.get(
        "provider",
        "local"
    )

    if provider_nome == "local":

        raise RuntimeError(
            "Provider online não está selecionado"
        )

    if not provider.get(
        "configured",
        False
    ):

        raise RuntimeError(
            "Provider online não está configurado"
        )

    prompt = construir_prompt_online(
        mensagem,
        conversation_id
    )

    lista_imagens = []

    if images:

        if isinstance(
            images,
            list
        ):

            for imagem in images:

                if imagem:

                    lista_imagens.append(
                        imagem
                    )

    if image and not lista_imagens:

        lista_imagens.append(
            image
        )

    try:

        resultado = provider_manager.responder(
            prompt,
            image=image,
            images=lista_imagens
        )

        if isinstance(
            resultado,
            dict
        ):

            if not resultado.get(
                "success",
                False
            ):

                raise RuntimeError(
                    resultado.get(
                        "error",
                        "Provider retornou erro"
                    )
                )

            texto = resultado.get(
                "reply",
                resultado.get(
                    "response",
                    ""
                )
            )

        else:

            texto = resultado

        texto = str(
            texto or ""
        ).strip()

        if not texto:

            raise RuntimeError(
                "Provider retornou resposta vazia"
            )

        return texto

    except TypeError:

        resultado = provider_manager.responder(
            prompt,
            image=image
        )

        if isinstance(
            resultado,
            dict
        ):

            if not resultado.get(
                "success",
                False
            ):

                raise RuntimeError(
                    resultado.get(
                        "error",
                        "Provider retornou erro"
                    )
                )

            texto = resultado.get(
                "reply",
                resultado.get(
                    "response",
                    ""
                )
            )

        else:

            texto = resultado

        texto = str(
            texto or ""
        ).strip()

        if not texto:

            raise RuntimeError(
                "Provider retornou resposta vazia"
            )

        return texto

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

        if not isinstance(dados, dict):

            return jsonify({
                "success": False,
                "error": "JSON inválido."
            }), 400

        provider = dados.get(
            "provider",
            ""
        )

        model = dados.get(
            "model",
            "auto"
        )

        if not isinstance(provider, str):

            return jsonify({
                "success": False,
                "error": "provider deve ser texto."
            }), 400

        resultado = provider_manager.selecionar(
            provider,
            model
        )

        return jsonify({
            "success": True,
            "engine": ENGINE_VERSION,
            "provider": resultado.get(
                "provider",
                provider
            ),
            "model": resultado.get(
                "model",
                model
            ),
            "configured": resultado.get(
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
            "success": False,
            "engine": ENGINE_VERSION,
            "error": str(erro)
        }), 400


# ============================================================
# CHAT PRINCIPAL
# ROUTER 06.1
# ============================================================

@app.post("/chat")
def chat():

    try:

        dados = request.get_json(
            silent=True
        )

        if not isinstance(dados, dict):

            return jsonify({
                "success": False,
                "engine": ENGINE_VERSION,
                "error": "JSON inválido."
            }), 400

        # ====================================================
        # TEXTO
        # ====================================================

        mensagem = dados.get(
            "message",
            dados.get(
                "mensagem",
                ""
            )
        )

        if not isinstance(
            mensagem,
            str
        ):

            mensagem = str(
                mensagem
            )

        mensagem = mensagem.strip()

        # ====================================================
        # CONVERSA
        # ====================================================

        conversation_id = dados.get(
            "conversation_id"
        )

        if conversation_id is not None:

            if not isinstance(
                conversation_id,
                str
            ):

                conversation_id = str(
                    conversation_id
                )

        # ====================================================
        # IMAGEM ÚNICA
        # ====================================================

        image = dados.get(
            "image"
        )

        if image is not None:

            if not isinstance(
                image,
                str
            ):

                image = None

            else:

                image = image.strip()

                if not image:

                    image = None

        # ====================================================
        # VÁRIAS IMAGENS
        # ====================================================

        images = dados.get(
            "images",
            []
        )

        if images is None:

            images = []

        if not isinstance(
            images,
            list
        ):

            return jsonify({

                "success": False,

                "engine":
                    ENGINE_VERSION,

                "error":
                    "images deve ser uma lista."

            }), 400

        imagens_validas = []

        for item in images:

            if not isinstance(
                item,
                str
            ):

                continue

            item = item.strip()

            if not item:

                continue

            imagens_validas.append(
                item
            )

        if image and image not in imagens_validas:

            imagens_validas.insert(
                0,
                image
            )

        # ====================================================
        # ÁUDIO
        # ====================================================

        audio = dados.get(
            "audio"
        )

        audio_format = dados.get(
            "audio_format",
            "m4a"
        )

        if audio is not None:

            if not isinstance(
                audio,
                str
            ):

                return jsonify({

                    "success":
                        False,

                    "engine":
                        ENGINE_VERSION,

                    "error":
                        "audio deve ser Base64 em texto."

                }), 400

            audio = audio.strip()

        # ====================================================
        # VÍDEO
        # ====================================================

        video = dados.get(
            "video"
        )

        # ====================================================
        # TIPO DE CONTEÚDO
        # ====================================================

        tem_texto = bool(
            mensagem
        )

        tem_imagens = bool(
            imagens_validas
        )

        tem_audio = bool(
            audio
        )

        tem_video = bool(
            video
        )

        if not (
            tem_texto
            or tem_imagens
            or tem_audio
            or tem_video
        ):

            return jsonify({

                "success":
                    False,

                "engine":
                    ENGINE_VERSION,

                "error":
                    "Mensagem vazia."

            }), 400

        # ====================================================
        # TRANSCRIÇÃO DE ÁUDIO
        # ====================================================

        transcricao = ""

        if tem_audio:

            try:

                transcricao = (
                    provider_manager
                    .transcrever_audio(
                        audio,
                        audio_format
                    )
                )

                transcricao = str(
                    transcricao or ""
                ).strip()

            except Exception as erro:

                print(
                    "ERRO STT:"
                )

                print(
                    repr(erro)
                )

                return jsonify({

                    "success":
                        False,

                    "engine":
                        ENGINE_VERSION,

                    "mode":
                        "audio_transcription_error",

                    "error":
                        str(erro)

                }), 503

            if transcricao:

                if mensagem:

                    mensagem = (
                        mensagem
                        + "\n\n"
                        + "[Transcrição do áudio]: "
                        + transcricao
                    )

                else:

                    mensagem = transcricao

        # ====================================================
        # VÍDEO
        # ====================================================

        if tem_video:

            return jsonify({

                "success":
                    False,

                "engine":
                    ENGINE_VERSION,

                "mode":
                    "video_not_supported_yet",

                "error":
                    (
                        "O suporte de vídeo foi recebido pela API, "
                        "mas ainda não está ligado ao provider atual."
                    )

            }), 501

        # ====================================================
        # PROVIDER
        # ====================================================

        provider = obter_provider()

        provider_nome = provider.get(
            "provider",
            "local"
        )

        provider_model = provider.get(
            "model",
            "local"
        )

        provider_configured = provider.get(
            "configured",
            False
        )

        modo = provider_nome

        fallback = False

        local_fallback = False

        router_errors = []

        resposta = None

        engine_conversa = None

        if conversation_id:

            engine_conversa = obter_conversa(
                conversation_id
            )

        # ====================================================
        # CRIAR CONVERSA AUTOMATICAMENTE
        # ====================================================

        if engine_conversa is None:

            conversation_id = criar_conversa()

            engine_conversa = obter_conversa(
                conversation_id
            )

        # ====================================================
        # PROVIDER LOCAL
        # ====================================================

        if provider_nome == "local":

            if tem_imagens:

                return jsonify({

                    "success":
                        False,

                    "engine":
                        ENGINE_VERSION,

                    "mode":
                        "image_not_supported",

                    "provider":
                        provider_nome,

                    "model":
                        provider_model,

                    "configured":
                        provider_configured,

                    "conversation_id":
                        conversation_id,

                    "error":
                        (
                            "O provider local não consegue "
                            "analisar imagens."
                        )

                }), 503

            resposta = responder_local(
                mensagem,
                conversation_id
            )

            modo = "local"

        # ====================================================
        # PROVIDER ONLINE
        # ====================================================

        else:

            if not provider_configured:

                return jsonify({

                    "success":
                        False,

                    "engine":
                        ENGINE_VERSION,

                    "mode":
                        "online_error",

                    "provider":
                        provider_nome,

                    "model":
                        provider_model,

                    "configured":
                        False,

                    "conversation_id":
                        conversation_id,

                    "error":
                        (
                            "O provider online não está configurado."
                        )

                }), 503

        try:
            resultado_router = responder_online(
                mensagem,
                conversation_id=conversation_id,
                image=image,
                images=imagens_validas
            )

            if isinstance(resultado_router, dict):

                resposta = resultado_router.get(
                    "response",
                    resultado_router.get(
                        "reply",
                        ""
                    )
                )

                provider_nome = resultado_router.get(
                    "provider",
                    provider_nome
                )

                provider_model = resultado_router.get(
                    "model",
                    provider_model
                )

            else:

                resposta = str(
                    resultado_router or ""
                ).strip()

            if not resposta:
                raise RuntimeError(
                    "O Router retornou uma resposta vazia."
                )

        except Exception as e:
            print("ERRO PROVIDER /chat:")
            print(repr(e))

            return jsonify({
                "success": False,
                "configured": True,
                "conversation_id": conversation_id,
                "engine": ENGINE_VERSION,
                "error": str(e),
                "mode": "online_error",
                "provider": provider_nome,
                "model": provider_model
            }), 503

        # ====================================================
        # GARANTIR RESPOSTA
        # ====================================================

        if resposta is None:

            resposta = (
                "Desculpa, não consegui gerar "
                "uma resposta agora. Tenta novamente."
            )

        resposta = str(
            resposta
        ).strip()

        if not resposta:

            resposta = (
                "Desculpa, não consegui gerar "
                "uma resposta agora. Tenta novamente."
            )

        # ====================================================
        # HISTÓRICO
        # ====================================================

        if engine_conversa is not None:

            if mensagem:

                engine_conversa.historico.adicionar_usuario(
                    mensagem
                )

            if tem_imagens:

                engine_conversa.historico.adicionar_usuario(
                    "[Imagem enviada]"
                )

            if tem_audio:

                engine_conversa.historico.adicionar_usuario(
                    "[Áudio enviado]"
                )

            engine_conversa.historico.adicionar_vany(
                resposta
            )

        # ====================================================
        # RESPOSTA
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

            "model":
                provider_model,

            "configured":
                provider_configured,

            "fallback":
                fallback,

            "local_fallback":
                local_fallback,

            "router_errors":
                router_errors,

            "conversation_id":
                conversation_id,

            "reply":
                resposta,

            "transcription":
                transcricao,

            "media":
                {
                    "images":
                        len(imagens_validas),

                    "audio":
                        tem_audio,

                    "video":
                        tem_video
                }

        })

    except Exception as erro:

        print(
            "ERRO /chat:"
        )

        print(
            repr(erro)
        )

        return jsonify({

            "success":
                False,

            "engine":
                ENGINE_VERSION,

            "mode":
                "server_error",

            "error":
                str(erro)

        }), 500



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
# VANY AUDIO - TEXT TO SPEECH
# ============================================================

@app.post("/audio/speech")
def audio_speech():

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

                "engine":
                    ENGINE_VERSION,

                "error":
                    "JSON inválido."

            }), 400

        texto = dados.get(
            "text",
            dados.get(
                "texto",
                ""
            )
        )

        if not isinstance(
            texto,
            str
        ):

            texto = str(
                texto
            )

        texto = texto.strip()

        if not texto:

            return jsonify({

                "success":
                    False,

                "engine":
                    ENGINE_VERSION,

                "error":
                    "Texto vazio."

            }), 400

        provider = obter_provider()

        if not provider.get(
            "configured",
            False
        ):

            return jsonify({

                "success":
                    False,

                "engine":
                    ENGINE_VERSION,

                "error":
                    "Provider não configurado."

            }), 503

        audio_base64 = (
            provider_manager
            .gerar_voz(
                texto
            )
        )

        audio_base64 = str(
            audio_base64 or ""
        ).strip()

        if not audio_base64:

            raise RuntimeError(
                "TTS retornou áudio vazio."
            )

        return jsonify({

            "success":
                True,

            "engine":
                ENGINE_VERSION,

            "provider":
                provider.get(
                    "provider",
                    "unknown"
                ),

            "model":
                provider.get(
                    "model",
                    "unknown"
                ),

            "audio_format":
                "mp3",

            "audio_base64":
                audio_base64

        })

    except Exception as erro:

        print(
            "ERRO /audio/speech:"
        )

        print(
            repr(erro)
        )

        return jsonify({

            "success":
                False,

            "engine":
                ENGINE_VERSION,

            "error":
                str(erro)

        }), 503
# ============================================================
# VANY AUDIO - SPEECH TO TEXT
# ============================================================

@app.post("/audio/transcribe")
def audio_transcribe():

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

                "engine":
                    ENGINE_VERSION,

                "error":
                    "JSON inválido."

            }), 400

        audio_base64 = dados.get(
            "audio",
            dados.get(
                "audio_base64",
                ""
            )
        )

        formato = dados.get(
            "format",
            dados.get(
                "audio_format",
                "m4a"
            )
        )

        if not isinstance(
            audio_base64,
            str
        ):

            return jsonify({

                "success":
                    False,

                "engine":
                    ENGINE_VERSION,

                "error":
                    "audio deve ser Base64."

            }), 400

        audio_base64 = audio_base64.strip()

        if not audio_base64:

            return jsonify({

                "success":
                    False,

                "engine":
                    ENGINE_VERSION,

                "error":
                    "Áudio vazio."

            }), 400

        texto = (
            provider_manager
            .transcrever_audio(
                audio_base64,
                formato
            )
        )

        texto = str(
            texto or ""
        ).strip()

        if not texto:

            raise RuntimeError(
                "STT retornou texto vazio."
            )

        return jsonify({

            "success":
                True,

            "engine":
                ENGINE_VERSION,

            "provider":
                obter_provider().get(
                    "provider",
                    "unknown"
                ),

            "text":
                texto

        })

    except Exception as erro:

        print(
            "ERRO /audio/transcribe:"
        )

        print(
            repr(erro)
        )

        return jsonify({

            "success":
                False,

            "engine":
                ENGINE_VERSION,

            "error":
                str(erro)

        }), 503

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

# ============================================================
# VANY CLOUD GAME v1 - ROUTES
# ============================================================

from vany_cloud_game import (
    cloud_game_health,
    create_user,
    get_user,
    list_games,
    get_game,
    list_servers,
    start_session,
    get_session,
    stop_session,
    get_history,
    get_plans,
    get_credits,
    set_server_status
)

# ------------------------------------------------------------
# CLOUD HEALTH
# ------------------------------------------------------------

@app.route("/cloud", methods=["GET"])
def cloud_game_status():
    return cloud_game_health()


# ------------------------------------------------------------
# GAMES
# ------------------------------------------------------------

@app.route("/cloud/games", methods=["GET"])
def cloud_games():
    return {
        "success": True,
        "games": list_games()
    }


@app.route("/cloud/games/<game_id>", methods=["GET"])
def cloud_game_details(game_id):
    game = get_game(game_id)

    if game is None:
        return {
            "success": False,
            "error": "game_not_found"
        }, 404

    return {
        "success": True,
        "game": game
    }


# ------------------------------------------------------------
# AUTH / USER
# ------------------------------------------------------------

@app.route("/cloud/auth/register", methods=["POST"])
def cloud_register():

    data = request.get_json(silent=True) or {}

    username = str(data.get("username", "")).strip()
    email = data.get("email")

    if not username:
        return {
            "success": False,
            "error": "username_required"
        }, 400

    return create_user(
        username=username,
        email=email
    )


@app.route("/cloud/auth/login", methods=["POST"])
def cloud_login():

    data = request.get_json(silent=True) or {}

    user_id = str(data.get("user_id", "")).strip()

    if not user_id:
        return {
            "success": False,
            "error": "user_id_required"
        }, 400

    user = get_user(user_id)

    if user is None:
        return {
            "success": False,
            "error": "user_not_found"
        }, 404

    return {
        "success": True,
        "user": user
    }


@app.route("/cloud/profile", methods=["GET"])
def cloud_profile():

    user_id = request.args.get("user_id", "").strip()

    if not user_id:
        return {
            "success": False,
            "error": "user_id_required"
        }, 400

    user = get_user(user_id)

    if user is None:
        return {
            "success": False,
            "error": "user_not_found"
        }, 404

    return {
        "success": True,
        "user": user
    }


# ------------------------------------------------------------
# SERVERS
# ------------------------------------------------------------

@app.route("/cloud/servers", methods=["GET"])
def cloud_servers():

    return {
        "success": True,
        "servers": list_servers()
    }


# ------------------------------------------------------------
# START SESSION
# ------------------------------------------------------------

@app.route("/cloud/sessions/start", methods=["POST"])
def cloud_start_session():

    data = request.get_json(silent=True) or {}

    user_id = str(data.get("user_id", "")).strip()
    game_id = str(data.get("game_id", "")).strip()

    if not user_id:
        return {
            "success": False,
            "error": "user_id_required"
        }, 400

    if not game_id:
        return {
            "success": False,
            "error": "game_id_required"
        }, 400

    result = start_session(
        user_id=user_id,
        game_id=game_id
    )

    if not result.get("success"):
        return result, 400

    return result


# ------------------------------------------------------------
# SESSION INFO
# ------------------------------------------------------------

@app.route("/cloud/sessions/<session_id>", methods=["GET"])
def cloud_session(session_id):

    session = get_session(session_id)

    if session is None:
        return {
            "success": False,
            "error": "session_not_found"
        }, 404

    return {
        "success": True,
        "session": session
    }


# ------------------------------------------------------------
# STOP SESSION
# ------------------------------------------------------------

@app.route("/cloud/sessions/<session_id>/stop", methods=["POST"])
def cloud_stop_session(session_id):

    result = stop_session(session_id)

    if not result.get("success"):
        return result, 404

    return result


# ------------------------------------------------------------
# HISTORY
# ------------------------------------------------------------

@app.route("/cloud/history", methods=["GET"])
def cloud_history():

    user_id = request.args.get("user_id", "").strip()

    if not user_id:
        return {
            "success": False,
            "error": "user_id_required"
        }, 400

    return {
        "success": True,
        "history": get_history(user_id)
    }


# ------------------------------------------------------------
# PLANS
# ------------------------------------------------------------

@app.route("/cloud/plans", methods=["GET"])
def cloud_plans():

    return {
        "success": True,
        "plans": get_plans()
    }


# ------------------------------------------------------------
# CREDITS
# ------------------------------------------------------------

@app.route("/cloud/credits", methods=["GET"])
def cloud_credits():

    user_id = request.args.get("user_id", "").strip()

    if not user_id:
        return {
            "success": False,
            "error": "user_id_required"
        }, 400

    return get_credits(user_id)


# ------------------------------------------------------------
# ADMIN SERVER STATUS
# ------------------------------------------------------------

@app.route("/cloud/admin/server/status", methods=["POST"])
def cloud_admin_server_status():

    data = request.get_json(silent=True) or {}

    server_id = str(data.get("server_id", "")).strip()
    status = str(data.get("status", "")).strip()

    if not server_id:
        return {
            "success": False,
            "error": "server_id_required"
        }, 400

    if not status:
        return {
            "success": False,
            "error": "status_required"
        }, 400

    return set_server_status(
        server_id=server_id,
        status=status
    )


# ============================================================
# VANY PREMIUM
# ============================================================

PREMIUM_PRICE = 499
PREMIUM_CURRENCY = "MZN"
PREMIUM_DAYS = 30


@app.route("/v1/account", methods=["GET"])
def v1_account():
    user_id = request.args.get("user_id")

    if not user_id:
        return jsonify({
            "success": False,
            "error": "user_id é obrigatório"
        }), 400

    user = premium_manager.get_user(user_id)

    if not user:
        return jsonify({
            "success": False,
            "error": "Utilizador não encontrado"
        }), 404

    return jsonify({
        "success": True,
        "account": user
    })


@app.route("/v1/premium/status", methods=["GET"])
def v1_premium_status():
    user_id = request.args.get("user_id")

    if not user_id:
        return jsonify({
            "success": False,
            "error": "user_id é obrigatório"
        }), 400

    user = premium_manager.get_user(user_id)

    if not user:
        return jsonify({
            "success": False,
            "error": "Utilizador não encontrado"
        }), 404

    premium_manager.check_expired(user_id)

    user = premium_manager.get_user(user_id)

    return jsonify({
        "success": True,
        "premium": {
            "plan": user["plan"],
            "status": user["premium_status"],
            "premium_until": user["premium_until"]
        }
    })


@app.route("/v1/premium/payment", methods=["POST"])
def v1_premium_payment():
    data = request.get_json(silent=True) or {}

    user_id = data.get("user_id")
    method = str(data.get("method", "")).lower().strip()

    if not user_id:
        return jsonify({
            "success": False,
            "error": "user_id é obrigatório"
        }), 400

    if method not in ("mpesa", "emola"):
        return jsonify({
            "success": False,
            "error": "Método de pagamento inválido. Use mpesa ou emola."
        }), 400

    user = premium_manager.get_user(user_id)

    if not user:
        return jsonify({
            "success": False,
            "error": "Utilizador não encontrado"
        }), 404

    payment = premium_manager.create_payment(
        user_id,
        method
    )

    return jsonify({
        "success": True,
        "message": "Pagamento criado. Aguardando confirmação.",
        "payment": payment
    }), 201


@app.route("/v1/premium/cancel", methods=["POST"])
def v1_premium_cancel():
    data = request.get_json(silent=True) or {}

    user_id = data.get("user_id")

    if not user_id:
        return jsonify({
            "success": False,
            "error": "user_id é obrigatório"
        }), 400

    user = premium_manager.get_user(user_id)

    if not user:
        return jsonify({
            "success": False,
            "error": "Utilizador não encontrado"
        }), 404

    result = premium_manager.cancel_payment(user_id)

    return jsonify({
        "success": True,
        "message": "Operação de pagamento cancelada.",
        "result": result
    })


# ============================================================
# VANY PREMIUM - CONFIRMAÇÃO DE TESTE
# ATENÇÃO: SOMENTE DESENVOLVIMENTO
# Não representa confirmação real do M-Pesa/e-Mola.
# ============================================================

@app.route("/v1/premium/test/confirm", methods=["POST"])
def v1_premium_test_confirm():
    data = request.get_json(silent=True) or {}

    payment_id = data.get("payment_id")

    if not payment_id:
        return jsonify({
            "success": False,
            "error": "payment_id é obrigatório"
        }), 400

    payment = premium_manager.get_payment(payment_id)

    if not payment:
        return jsonify({
            "success": False,
            "error": "Pagamento não encontrado"
        }), 404

    if payment["status"] != "pending":
        return jsonify({
            "success": False,
            "error": "O pagamento não está pendente",
            "status": payment["status"]
        }), 400

    user = premium_manager.confirm_payment(payment_id)

    return jsonify({
        "success": True,
        "test": True,
        "message": "Pagamento confirmado em modo de teste.",
        "payment": premium_manager.get_payment(payment_id),
        "account": user
    })


# ============================================================
# VANY PREMIUM - ACESSO E RECURSOS
# ============================================================

@app.route("/v1/premium/access", methods=["GET"])
def v1_premium_access():
    user_id = request.args.get("user_id")

    if not user_id:
        return jsonify({
            "success": False,
            "error": "user_id é obrigatório"
        }), 400

    access = get_premium_access(user_id)

    return jsonify({
        "success": True,
        "access": access,
        "features": {
            "basic_chat": True,
            "premium_chat": access["allowed"],
            "advanced_ai": access["allowed"],
            "priority_processing": access["allowed"],
            "premium_tools": access["allowed"]
        }
    })

# ============================================================
# VANY IA — GOOGLE LOGIN
# ============================================================

@app.route(
    "/auth/google/start",
    methods=["GET"]
)
def auth_google_start():

    try:

        if not os.environ.get(
            "GOOGLE_CLIENT_ID",
            ""
        ).strip():

            return jsonify({
                "success": False,
                "error": "GOOGLE_CLIENT_ID não configurado."
            }), 500

        redirect_uri = GOOGLE_REDIRECT_URI

        return google.authorize_redirect(
            redirect_uri
        )

    except Exception as erro:

        print(
            "ERRO /auth/google/start:",
            repr(erro)
        )

        return jsonify({
            "success": False,
            "error": "Não foi possível iniciar o Google Login.",
            "details": str(erro)
        }), 500


@app.route(
    "/auth/google/callback",
    methods=["GET"]
)
def auth_google_callback():

    try:

        token = google.authorize_access_token()

        if not token:

            return jsonify({
                "success": False,
                "error": "Token Google não recebido."
            }), 400

        userinfo = token.get("userinfo")

        if not userinfo:

            userinfo = google.userinfo()

        google_sub = str(
            userinfo.get(
                "sub",
                ""
            )
        ).strip()

        email = str(
            userinfo.get(
                "email",
                ""
            )
        ).strip()

        name = str(
            userinfo.get(
                "name",
                ""
            )
        ).strip()

        picture = str(
            userinfo.get(
                "picture",
                ""
            )
        ).strip()

        if not google_sub:

            return jsonify({
                "success": False,
                "error": "Google não enviou o identificador da conta."
            }), 400

        # ----------------------------------------------------
        # Procurar conta Google existente
        # ----------------------------------------------------

        with sqlite3.connect(
            GOOGLE_AUTH_DATABASE
        ) as db:

            row = db.execute("""
                SELECT user_id
                FROM google_users
                WHERE google_sub = ?
                LIMIT 1
            """, (
                google_sub,
            )).fetchone()

        if row:

            user_id = row[0]

        else:

            # ------------------------------------------------
            # Criar utilizador Vany
            # ------------------------------------------------

            username = (
                name
                if name
                else (
                    email.split("@")[0]
                    if "@" in email
                    else "Utilizador Vany"
                )
            )

            resultado = create_user(
                username=username,
                email=email
            )

            if not resultado.get(
                "success",
                False
            ):

                # Pode já existir pelo email
                user_existente = None

                if email:

                    with sqlite3.connect(
                        "vany_cloud_game.db"
                    ) as db:

                        row = db.execute("""
                            SELECT user_id
                            FROM cloud_users
                            WHERE email = ?
                            LIMIT 1
                        """, (
                            email,
                        )).fetchone()

                    if row:
                        user_existente = row[0]

                if not user_existente:

                    return jsonify({
                        "success": False,
                        "error": "Não foi possível criar a conta Vany.",
                        "details": resultado
                    }), 500

                user_id = user_existente

            else:

                user = resultado.get(
                    "user",
                    resultado
                )

                user_id = str(
                    user.get(
                        "user_id",
                        ""
                    )
                ).strip()

            if not user_id:

                return jsonify({
                    "success": False,
                    "error": "ID Vany não foi criado."
                }), 500

            # ------------------------------------------------
            # Associar Google → Vany
            # ------------------------------------------------

            with sqlite3.connect(
                GOOGLE_AUTH_DATABASE
            ) as db:

                db.execute("""
                    INSERT OR REPLACE INTO google_users
                    (
                        google_sub,
                        user_id,
                        email,
                        name,
                        picture,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    google_sub,
                    user_id,
                    email,
                    name,
                    picture,
                    str(time.time())
                ))

                db.commit()

        # ----------------------------------------------------
        # Atualizar dados da conta Google
        # ----------------------------------------------------

        with sqlite3.connect(
            GOOGLE_AUTH_DATABASE
        ) as db:

            db.execute("""
                UPDATE google_users
                SET email = ?,
                    name = ?,
                    picture = ?
                WHERE google_sub = ?
            """, (
                email,
                name,
                picture,
                google_sub
            ))

            db.commit()

        # ----------------------------------------------------
        # Criar código temporário de retorno
        # ----------------------------------------------------

        code = secrets.token_urlsafe(32)

        with sqlite3.connect(
            GOOGLE_AUTH_DATABASE
        ) as db:

            db.execute("""
                INSERT INTO google_codes
                (
                    code,
                    user_id,
                    created_at,
                    used
                )
                VALUES (?, ?, ?, 0)
            """, (
                code,
                user_id,
                time.time()
            ))

            db.commit()

        # ----------------------------------------------------
        # Retorno para a aplicação Android
        # ----------------------------------------------------

        return redirect(
            "vany://oauth"
            "?code="
            + code
        )

    except Exception as erro:

        print(
            "ERRO /auth/google/callback:",
            repr(erro)
        )

        return jsonify({
            "success": False,
            "error": "Erro ao concluir o login Google.",
            "details": str(erro)
        }), 500
# ============================================================
# VANY IA — TROCAR CÓDIGO GOOGLE POR SESSÃO
# ============================================================

@app.route(
    "/auth/google/exchange",
    methods=["POST"]
)
def auth_google_exchange():

    try:

        data = request.get_json(
            silent=True
        ) or {}

        code = str(
            data.get(
                "code",
                ""
            )
        ).strip()

        if not code:

            return jsonify({
                "success": False,
                "error": "code_required"
            }), 400

        with sqlite3.connect(
            GOOGLE_AUTH_DATABASE
        ) as db:

            row = db.execute("""
                SELECT
                    user_id,
                    created_at,
                    used
                FROM google_codes
                WHERE code = ?
                LIMIT 1
            """, (
                code,
            )).fetchone()

            if not row:

                return jsonify({
                    "success": False,
                    "error": "invalid_code"
                }), 401

            user_id = row[0]
            created_at = float(row[1])
            used = int(row[2])

            # Código válido por 5 minutos
            if time.time() - created_at > 300:

                db.execute("""
                    DELETE FROM google_codes
                    WHERE code = ?
                """, (
                    code,
                ))

                db.commit()

                return jsonify({
                    "success": False,
                    "error": "code_expired"
                }), 401

            if used:

                return jsonify({
                    "success": False,
                    "error": "code_already_used"
                }), 401

            db.execute("""
                UPDATE google_codes
                SET used = 1
                WHERE code = ?
            """, (
                code,
            ))

            db.commit()

        user = get_user(
            user_id
        )

        if user is None:

            return jsonify({
                "success": False,
                "error": "user_not_found"
            }), 404

        return jsonify({
            "success": True,
            "user": user
        })

    except Exception as erro:

        print(
            "ERRO /auth/google/exchange:",
            repr(erro)
        )

        return jsonify({
            "success": False,
            "error": "exchange_error",
            "details": str(erro)
        }), 500

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
