"""Gerenciamento de conteudos do professor/coordenacao.

Substitui os dois itens que antes ficavam separados no menu: "Gerenciar
Aulas" (exemplos de golpe) e "Gerenciar Modulos". A pagina mostra um
seletor e desenha a pagina escolhida, sem duplicar a logica de cada uma.
"""

import streamlit as st

from modules.gerenciar_modulos import render_gerenciar_modulos
from modules.pergaminhos import render_gerenciar_crime

OPCOES = ["Exemplos de Golpe", "Módulos"]
CHAVE_ABA = "gerenciar_conteudos_aba"


def render_gerenciar_conteudos():
    """Desenha a pagina unica de gerenciamento de conteudos."""
    with st.container(key="conteudo_gerenciar_conteudos"):
        _render_gerenciar_conteudos()


def _render_gerenciar_conteudos():
    st.title("🗂️ Gerenciar Conteúdos")
    st.caption(
        "Escolha o tipo de conteúdo que você quer publicar, editar ou "
        "inativar."
    )

    aba = st.radio(
        "Tipo de conteúdo",
        OPCOES,
        horizontal=True,
        key=CHAVE_ABA,
        label_visibility="collapsed",
    )
    st.divider()

    if aba == "Exemplos de Golpe":
        with st.container(key="aba_gerenciar_exemplos_golpe"):
            render_gerenciar_crime()
    else:
        with st.container(key="aba_gerenciar_modulos"):
            render_gerenciar_modulos()
