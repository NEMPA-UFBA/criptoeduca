"""Pagina individual de um modulo de aprendizagem.

Esta e a pagina que abre quando o aluno clica em "Iniciar modulo" no mapa de
missoes (modules/mainmenu.py). Ela reune, na mesma tela:

  - o cabecalho do modulo (titulo, nivel, dificuldade, tempo);
  - o material de leitura em PDF;
  - o quiz do modulo, logo abaixo do material.

O esqueleto desta pagina ja existe para a navegacao funcionar. As secoes de
material e de quiz entram nas etapas seguintes da missao (visualizacao dos
PDFs e integracao do quiz).
"""

import html

import streamlit as st

from modules.estilo import aplicar_estilo, html_bruto
from modules.modulos import modulo_por_slug, pdf_disponivel


def render_pagina_modulo(slug):
    """Desenha a pagina do modulo com aquele slug."""
    aplicar_estilo()

    modulo = modulo_por_slug(slug)
    if modulo is None:
        # Slug invalido na sessao: acontece se o manifesto mudar entre uma
        # sessao aberta e a proxima. Nao derruba o app -- volta para o mapa.
        st.warning("Módulo não encontrado. Voltando para o mapa de missões.")
        st.session_state.pop("modulo_selecionado", None)
        st.rerun()
        return

    # Voltar para o mapa. O botao fica antes do cabecalho porque e a acao
    # de onde a pessoa veio.
    if st.button("⬅️ Voltar ao mapa de missões", key="voltar_mapa_modulos"):
        st.session_state.pop("modulo_selecionado", None)
        st.rerun()

    cor = html.escape(modulo.get("cor", "#4F46E5"))
    icone = html.escape(modulo.get("icone", "📘"))
    titulo = html.escape(modulo.get("titulo", ""))
    resumo = html.escape(modulo.get("resumo", ""))
    nivel = html.escape(modulo.get("nivel", ""))
    dificuldade = html.escape(modulo.get("dificuldade", ""))
    duracao = html.escape(modulo.get("duracao", ""))

    st.markdown(
        html_bruto(
            f"""
            <div class="ce-modulo-cabecalho" style="--ce-cor-modulo: {cor}">
              <h2>{icone} {titulo}</h2>
              <p>{resumo}</p>
              <div class="ce-tags">
                <span class="ce-badge ce-badge-nivel">{nivel}</span>
                <span class="ce-badge">📖 {dificuldade}</span>
                <span class="ce-badge">⏱️ {duracao}</span>
              </div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

    # --- Material de leitura ---
    # A visualizacao do PDF entra na proxima etapa. Por enquanto a pagina
    # diz se o arquivo existe, para a equipe saber o que falta colocar na
    # pasta static/modulos/.
    st.subheader("📖 Material de leitura")
    if pdf_disponivel(modulo):
        st.info("PDF disponível — a visualização entra na próxima etapa.")
    else:
        st.markdown(
            html_bruto(
                f"""
                <div class="ce-aviso">📄 O material deste módulo ainda está em preparação. O PDF deve ser colocado em <code>static/modulos/{html.escape(modulo.get('pdf', '').split('/')[-1])}</code>.</div>
                """
            ),
            unsafe_allow_html=True,
        )

    # --- Quiz ---
    st.subheader("🧠 Quiz do módulo")
    st.info("O quiz entra na próxima etapa, dentro desta mesma página.")
