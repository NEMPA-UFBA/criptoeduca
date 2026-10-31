"""Notificação da simulação educativa de anúncio cripto."""

import time
from urllib.parse import quote

import streamlit as st


_CHAVE_INICIO = "_ce_anuncio_inicio_monotonic"
_CHAVE_EXIBIDO = "_ce_anuncio_exibido"


def _mostrar_notificacao() -> None:
    caminho = quote("simulaçao-golpe/simulacao-golpe.html")
    url = f"/app/static/{caminho}"
    st.toast(
        "**Oportunidade exclusiva!** Multiplique seu dinheiro em 30 dias. "
        f"[Conferir agora →]({url})",
        icon="🔔",
        duration="infinite",
    )


@st.fragment(run_every="1s")
def _verificar_tempo() -> None:
    """Exibe a notificação após dois minutos, sem depender de JavaScript."""
    if _CHAVE_EXIBIDO in st.session_state:
        return

    inicio = st.session_state.setdefault(_CHAVE_INICIO, time.monotonic())
    if time.monotonic() - inicio >= 120:
        st.session_state[_CHAVE_EXIBIDO] = True
        _mostrar_notificacao()


def render_anuncio_simulado(forcar: bool = False) -> None:
    """Ativa o temporizador e permite disparar a notificação pelo botão."""
    if forcar:
        st.session_state[_CHAVE_EXIBIDO] = True
        _mostrar_notificacao()
    _verificar_tempo()
