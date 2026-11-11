"""Pagina individual de um modulo de aprendizagem.

Esta e a pagina que abre quando o aluno clica em "Iniciar modulo" no mapa de
missoes (modules/mainmenu.py). Ela reune, na mesma tela:

  - o cabecalho do modulo (titulo, nivel, dificuldade, tempo);
  - o atalho para o material de leitura, que abre a pagina de leitura;
  - o quiz do modulo, liberado depois que a leitura e concluida.

O modulo especial do laboratorio AES segue o mesmo fluxo: leitura, quiz e,
so depois dos dois, o botao que abre o laboratorio de cifrar e decifrar.
"""

import html

import streamlit as st

from modules.database import carregar_estado_modulos
from modules.estilo import aplicar_estilo, html_bruto
from modules.criptografia_aes import render_laboratorio_aes
from modules.modulos import modulo_por_slug, pdf_disponivel
from modules.leitura import abrir_leitura, quiz_liberado
from modules.quiz import render_quiz


def _voltar_ao_mapa():
    """Limpa o modulo aberto; o rerun natural do clique redesenha o mapa."""
    st.session_state.pop("modulo_selecionado", None)


def _abrir_laboratorio(chave):
    st.session_state[chave] = True


def _fechar_laboratorio(chave):
    st.session_state[chave] = False


def _modulo_concluido(slug):
    """Diz se o aluno ja leu o material e respondeu ao quiz do modulo.

    O laboratorio AES so libera depois das duas coisas: a leitura marca o
    modulo em "leituras", e o quiz grava uma tentativa em
    "progresso_modulos". Uma sem a outra nao basta.
    """
    username = st.session_state.get("username")
    if not username:
        return False
    try:
        progresso, lidos = carregar_estado_modulos(username)
    except Exception:
        return False
    return slug in lidos and slug in progresso


def _render_laboratorio_especial(slug):
    """Mostra o botao do laboratorio AES e, ao abrir, o laboratorio."""
    st.divider()
    st.subheader("🧪 Laboratório AES-128-GCM")

    if not _modulo_concluido(slug):
        st.markdown(
            html_bruto(
                """
                <div class="ce-aviso">🔒 <strong>O laboratório está
                bloqueado.</strong> Conclua a leitura do material e responda
                ao quiz para liberar o botão de teste.</div>
                """
            ),
            unsafe_allow_html=True,
        )
        return

    st.caption(
        "Você concluiu a leitura e o quiz. Agora pode cifrar e decifrar "
        "mensagens de verdade — nada é publicado no mural."
    )

    chave_aberto = "aes_lab_aberto_%s" % slug
    if not st.session_state.get(chave_aberto):
        st.button(
            "🧪 Testar o laboratório AES",
            key="abrir_lab_%s" % slug,
            type="primary",
            on_click=_abrir_laboratorio,
            args=(chave_aberto,),
        )
        return

    st.button(
        "Fechar o laboratório",
        key="fechar_lab_%s" % slug,
        on_click=_fechar_laboratorio,
        args=(chave_aberto,),
    )

    render_laboratorio_aes()


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

    with st.container(key=f"pagina_modulo_{slug}"):
        _render_conteudo_modulo(modulo, slug)


def _render_conteudo_modulo(modulo, slug):
    # Voltar para o mapa. O botao fica antes do cabecalho porque e a acao
    # de onde a pessoa veio.
    st.button(
        "⬅️ Voltar ao mapa de missões",
        key=f"voltar_mapa_modulos_{slug}",
        on_click=_voltar_ao_mapa,
    )

    cor = html.escape(modulo.get("cor", "#4F46E5"))
    icone = html.escape(modulo.get("icone", "📘"))
    titulo = html.escape(modulo.get("titulo", ""))
    resumo = html.escape(modulo.get("resumo", ""))
    nivel = html.escape(modulo.get("nivel", ""))
    dificuldade = html.escape(modulo.get("dificuldade", ""))
    duracao = html.escape(modulo.get("duracao", ""))
    badge_especial = (
        '<span class="ce-badge">🧪 Laboratório</span>'
        if modulo.get("especial")
        else ""
    )

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
                {badge_especial}
              </div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

    # --- Material de leitura ---
    #
    # O PDF NAO aparece aqui. Ele aparece na PAGINA DE LEITURA, que e
    # onde o aluno le o material e aperta "Concluir a leitura" para
    # liberar o quiz. Mostrar o PDF aqui dava duas saidas para o mesmo
    # material: o aluno lia o PDF na pagina do modulo e, sem querer,
    # achava que ja tinha lido -- o que e justamente o que a leitura
    # existe para impedir.
    #
    # O que fica aqui e o aviso de que o material existe e o botao que
    # leva ate ele.
    st.subheader("📖 Material de leitura")
    if pdf_disponivel(modulo):
        st.caption(
            "O material deste módulo fica na **página de leitura**. É lá que "
            "você lê e marca a leitura como concluída."
        )
    else:
        st.markdown(
            html_bruto(
                f"""
                <div class="ce-aviso">📄 O material deste módulo ainda está em preparação. O PDF deve ser colocado em <code>static/modulos/{html.escape(modulo.get('pdf', '').split('/')[-1])}</code>.</div>
                """
            ),
            unsafe_allow_html=True,
        )

    # O botao que abre a pagina de leitura. E o que separa "ver o
    # material" de "ler o material": so quem aperta este botao chega na
    # pagina com o "Concluir a leitura", e e aperta-lo que libera o
    # quiz.
    st.markdown("")
    st.button(
        "📖 Abrir a página de leitura",
        key="abrir_leitura_%s" % modulo.get("slug", ""),
        type="primary",
        on_click=abrir_leitura,
        args=(modulo.get("slug", ""),),
    )

    st.divider()

    # --- Quiz ---
    #
    # O quiz so aparece depois da leitura. O bloqueio nao e uma
    # surpresa: a tela diz o que fazer para liberar.
    if quiz_liberado(modulo.get("slug", "")):
        render_quiz(modulo, modulo.get("slug", ""))
    else:
        st.markdown(
            html_bruto(
                """
                <div class="ce-aviso">🔒 <strong>O quiz deste módulo está
                bloqueado.</strong> Termine a leitura do material e aperte
                <em>Concluir a leitura</em> na página de leitura para
                liberar.</div>
                """
            ),
            unsafe_allow_html=True,
        )

    # --- Laboratorio especial ---
    #
    # O laboratorio AES e a recompensa do modulo: o botao so aparece
    # depois que o aluno leu o material e respondeu ao quiz. Fica no fim
    # da pagina, depois do resultado do quiz.
    if modulo.get("especial") == "aes":
        _render_laboratorio_especial(modulo.get("slug", ""))
