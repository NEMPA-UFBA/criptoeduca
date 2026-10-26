"""Pagina individual de um modulo de aprendizagem.

Esta e a pagina que abre quando o aluno clica em "Iniciar modulo" no mapa de
missoes (modules/mainmenu.py). Ela reune, na mesma tela:

  - o cabecalho do modulo (titulo, nivel, dificuldade, tempo);
  - o material de leitura em PDF, exibido dentro da propria pagina;
  - o quiz do modulo, logo abaixo do material.

O material e exibido num <iframe> com o PDF servido pelo proprio
Streamlit, mais um botao para baixar o arquivo. Nao existe widget
nativo de PDF no Streamlit -- nao ha st.pdf -- entao o embed era a
opcao que mantem a leitura dentro da pagina do modulo.
"""

import html
from urllib.parse import quote

import streamlit as st

from modules.estilo import aplicar_estilo, html_bruto
from modules.modulos import modulo_por_slug, pdf_disponivel, caminho_pdf
from modules.leitura import abrir_leitura, quiz_liberado
from modules.quiz import render_quiz


def bytes_do_pdf(modulo):
    """Le o arquivo do PDF do módulo e devolve os bytes.

    Devolve None quando o arquivo não está na pasta: quem chama já
    checou com pdf_disponivel, mas a checagem é feita duas vezes porque
    entre uma e outra o arquivo pode sumir. Um None aqui vira um erro
    claro na tela, e não um traceback.
    """
    caminho = caminho_pdf(modulo)
    if not caminho:
        return None
    try:
        with open(caminho, "rb") as arquivo:
            return arquivo.read()
    except OSError:
        return None


# Altura, em pixels, do visor do PDF dentro da pagina.
#
# O visor e um <iframe> com o PDF do Streamlit. Nao existe widget nativo de
# PDF no Streamlit -- nao ha st.pdf -- entao as duas opcoes sao o embed ou
# um link para abrir em outra aba. O embed foi escolhido porque a leitura
# acontece sem sair da pagina do modulo, que e o que o aluno quer.
ALTURA_PDF = 820


def _url_publica_do_pdf(modulo):
    """URL publica do PDF do modulo.

    O Streamlit serve a pasta "static" em /app/static/. Como o PDF fica
    dentro dela, o caminho publico e o mesmo arquivo com o prefixo.

    O nome do arquivo vem do manifesto, entao pode ter acento ou espaco
    (o "pdf" aceita caminho com pasta). A URL precisa disso codificado,
    e nao cru: um espaco quebra a requisição.
    """
    caminho = modulo.get("pdf") or ""
    if "/" in caminho:
        caminho = caminho.rsplit("/", 1)[-1]
    return "/app/static/modulos/" + quote(caminho)


def _mostrar_pdf(modulo):
    """Desenha o PDF do módulo, com um botão para baixar.

    O botão de baixar fica logo acima do visor porque nem todo
    navegador mostra a barra de ferramentas do leitor embutido, e o
    aluno precisa de um caminho para abrir o arquivo na mão.

    ESTA FUNCAO NAO E USADA NA PAGINA DO MODULO. O PDF fica na pagina de
    leitura (modules/leitura.py). Aqui ela continua caso o material
    precise ser mostrado em outro lugar.
    """
    url = _url_publica_do_pdf(modulo)
    conteudo = bytes_do_pdf(modulo)

    if conteudo is None:
        st.error(
            "O material deste módulo sumiu da pasta `static/modulos/`. "
            "Recarregue a página (F5) para tentar de novo."
        )
        return

    with st.container(key="modulo_material"):
        st.download_button(
            "⬇️ Baixar o material (PDF)",
            data=conteudo,
            file_name=(modulo.get("pdf") or "material.pdf").rsplit("/", 1)[-1],
            mime="application/pdf",
            key="baixar_material_modulo",
        )

        st.markdown(
            html_bruto(
                f"""
                <iframe
                    src="{html.escape(url)}"
                    width="100%"
                    height="{ALTURA_PDF}"
                    style="border:1px solid rgba(148, 163, 184, 0.25);
                           border-radius:12px;
                           background:#1e293b;"
                    title="Material de leitura do módulo">
                </iframe>
                """
            ),
            unsafe_allow_html=True,
        )


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
    if st.button(
        "📖 Abrir a página de leitura",
        key="abrir_leitura_%s" % modulo.get("slug", ""),
        type="primary",
    ):
        abrir_leitura(modulo.get("slug", ""))
        st.rerun()

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
