# ============================================================
# VANY WEB ENGINE 01
# Pesquisa e leitura de páginas web
# ============================================================

import requests
import socket
import ipaddress

from urllib.parse import urlparse, urljoin, quote_plus
from bs4 import BeautifulSoup


USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 13) "
    "AppleWebKit/537.36 Chrome/131.0 Safari/537.36"
)

TIMEOUT = 15
MAX_HTML = 1_500_000


# ============================================================
# SEGURANÇA DE URL
# ============================================================

def validar_url(url):

    try:
        parsed = urlparse(url)

        if parsed.scheme not in ("http", "https"):
            return False

        if not parsed.hostname:
            return False

        if parsed.username or parsed.password:
            return False

        host = parsed.hostname.lower()

        if host in ("localhost", "localhost.localdomain"):
            return False

        try:
            ips = [ipaddress.ip_address(host)]
        except ValueError:
            try:
                infos = socket.getaddrinfo(
                    host,
                    None,
                    type=socket.SOCK_STREAM
                )

                ips = [
                    ipaddress.ip_address(info[4][0])
                    for info in infos
                ]

            except Exception:
                return False

        if not ips:
            return False

        for ip in ips:

            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
                or ip.is_unspecified
            ):
                return False

        return True

    except Exception:
        return False


# ============================================================
# DOWNLOAD SEGURO DE PÁGINA
# ============================================================

def baixar_pagina(url):

    atual = url

    for _ in range(4):

        if not validar_url(atual):
            raise ValueError("URL não permitida ou insegura.")

        resposta = requests.get(
            atual,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,text/plain"
            },
            timeout=TIMEOUT,
            allow_redirects=False,
            stream=True
        )

        if resposta.status_code in (
            301, 302, 303, 307, 308
        ):

            destino = resposta.headers.get("Location")

            resposta.close()

            if not destino:
                raise ValueError("Redirecionamento inválido.")

            atual = urljoin(atual, destino)
            continue

        resposta.raise_for_status()

        tipo = resposta.headers.get(
            "Content-Type", ""
        ).lower()

        if (
            "text/html" not in tipo
            and "text/plain" not in tipo
        ):
            resposta.close()
            raise ValueError(
                "Este endereço não contém HTML ou texto."
            )

        tamanho = resposta.headers.get("Content-Length")

        if tamanho and int(tamanho) > MAX_HTML:
            resposta.close()
            raise ValueError("Página demasiado grande.")

        partes = []
        total = 0

        try:

            for bloco in resposta.iter_content(8192):

                if not bloco:
                    continue

                total += len(bloco)

                if total > MAX_HTML:
                    raise ValueError(
                        "Página excede o limite de tamanho."
                    )

                partes.append(bloco)

        finally:
            resposta.close()

        return atual, b"".join(partes)

    raise ValueError("Demasiados redirecionamentos.")


# ============================================================
# PESQUISA WEB
# ============================================================

def pesquisar_web(query, limite=8):

    query = str(query or "").strip()

    if not query:
        raise ValueError("Escreva o que deseja pesquisar.")

    limite = max(1, min(int(limite), 10))

    url = (
        "https://html.duckduckgo.com/html/?q="
        + quote_plus(query)
    )

    resposta = requests.get(
        url,
        headers={
            "User-Agent": USER_AGENT
        },
        timeout=TIMEOUT
    )

    resposta.raise_for_status()

    soup = BeautifulSoup(
        resposta.text,
        "html.parser"
    )

    resultados = []

    for item in soup.select(".result"):

        link = item.select_one(".result__a")

        if not link:
            continue

        titulo = link.get_text(
            " ", strip=True
        )

        href = link.get("href", "")

        if not titulo or not href:
            continue

        destino = urlparse(href)

        if destino.hostname and (
            "duckduckgo.com" in destino.hostname
        ):

            destino_url = (
                destino.query
            )

            from urllib.parse import parse_qs

            destino_url = parse_qs(
                destino_url
            ).get("uddg", [None])[0]

            if destino_url:
                href = destino_url

        if not validar_url(href):
            continue

        resumo_elemento = item.select_one(
            ".result__snippet"
        )

        resumo = (
            resumo_elemento.get_text(
                " ", strip=True
            )
            if resumo_elemento
            else ""
        )

        resultados.append({
            "title": titulo,
            "url": href,
            "snippet": resumo
        })

        if len(resultados) >= limite:
            break

    return {
        "success": True,
        "engine": "Vany Web Engine 01",
        "query": query,
        "count": len(resultados),
        "results": resultados
    }


# ============================================================
# ABRIR E LER PÁGINA
# ============================================================

def abrir_web(url):

    url = str(url or "").strip()

    if not url:
        raise ValueError("URL não informada.")

    final_url, conteudo = baixar_pagina(url)

    soup = BeautifulSoup(
        conteudo,
        "html.parser"
    )

    titulo = (
        soup.title.get_text(" ", strip=True)
        if soup.title
        else ""
    )

    for elemento in soup([
        "script",
        "style",
        "nav",
        "footer",
        "header",
        "noscript",
        "iframe"
    ]):
        elemento.decompose()

    texto = soup.get_text(
        " ", strip=True
    )

    texto = " ".join(texto.split())
    texto = texto[:12000]

    titulo_normalizado = titulo.lower()
    texto_normalizado = texto.lower()

    indicadores_bloqueio = [
        "client challenge",
        "access denied",
        "403 forbidden",
        "checking your browser",
        "verify you are human",
        "please enable javascript",
        "enable javascript and cookies",
        "request blocked",
        "attention required! | cloudflare",
        "security check",
        "captcha",
        "robot check"
    ]

    bloqueada = any(
        indicador in titulo_normalizado
        or indicador in texto_normalizado[:1200]
        for indicador in indicadores_bloqueio
    )

    if bloqueada:
        return {
            "success": False,
            "engine": "Vany Web Engine 01",
            "title": titulo,
            "url": final_url,
            "content": "",
            "characters": 0,
            "error": "Página bloqueada ou desafio anti-bot."
        }

    if not texto.strip():
        return {
            "success": False,
            "engine": "Vany Web Engine 01",
            "title": titulo,
            "url": final_url,
            "content": "",
            "characters": 0,
            "error": "Página sem conteúdo textual extraível."
        }

    return {
        "success": True,
        "engine": "Vany Web Engine 01",
        "title": titulo,
        "url": final_url,
        "content": texto,
        "characters": len(texto)
    }


print("Vany Web Engine 01 carregado.")
