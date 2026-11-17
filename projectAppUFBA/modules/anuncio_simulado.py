"""Notificação da simulação educativa de anúncio cripto."""

import time
from urllib.parse import urlparse

import streamlit as st


_CHAVE_INICIO = "_ce_anuncio_inicio_monotonic"
_CHAVE_EXIBIDO = "_ce_anuncio_exibido"


def _mostrar_notificacao() -> None:
    host = urlparse(st.context.url).hostname
    prefixo_proxy = "" if host in {"localhost", "127.0.0.1", "::1"} else "/~/+"
    url = f"{prefixo_proxy}/app/static/simulacao-golpe/simulacao-golpe.html"
    st.toast(
        "**Oportunidade exclusiva!** Multiplique seu dinheiro em 30 dias. "
        f"[Conferir agora →]({url})",
        icon="🔔",
        duration="infinite",
    )


# 30 s, e nao 5 s: sao 4 verificacoes por usuario em vez de 24 ate o aviso
# aparecer. O pop-up pode chegar ate 30 s depois dos dois minutos, o que nao
# muda nada numa simulacao de anuncio.
@st.fragment(run_every="30s")
def _verificar_tempo() -> None:
    """Exibe a notificação após dois minutos, sem depender de JavaScript."""
    if _CHAVE_EXIBIDO in st.session_state or _CHAVE_INICIO not in st.session_state:
        return

    inicio = st.session_state[_CHAVE_INICIO]
    if time.monotonic() - inicio >= 120:
        st.session_state[_CHAVE_EXIBIDO] = True
        # O toast pode ser desenhado pelo proprio fragmento; nao precisa
        # de um rerun do app inteiro so para mostra-lo.
        _mostrar_notificacao()


def render_anuncio_simulado(forcar: bool = False) -> None:
    """Ativa o temporizador e permite disparar a notificação pelo botão."""
    if forcar:
        st.session_state[_CHAVE_EXIBIDO] = True
        _mostrar_notificacao()
        return

    if _CHAVE_EXIBIDO in st.session_state:
        return

    if _CHAVE_INICIO not in st.session_state:
        st.session_state[_CHAVE_INICIO] = time.monotonic()
    _verificar_tempo()
