"""A pagina de leitura: o material do modulo, e o botao que libera o quiz.

O que o aluno faz:

    pagina do modulo  ->  "Abrir a pagina de leitura"  ->  le o material
    ->  "Concluir a leitura"  ->  volta para a pagina do modulo, agora com
    o quiz liberado.

Por que a leitura e uma PAGINA DO APP e nao um arquivo solto na pasta
static:

Because uma pagina estatica quebraria o login. A sessao do Streamlit
morre quando o navegador sai do app e volta: o aluno voltaria para a
tela de login, teria que entrar de novo, e o modulo que ele estava
lendo seria outro. Isso foi medido no navegador, nao e teoria.

Entao a leitura acontece aqui, dentro do app, e o que separa as duas
paginas e o estado da sessao: "estou lendo o modulo X" fica em
st.session_state, e o app desenha a pagina de leitura em vez da pagina
do modulo enquanto isso estiver marcado.

O botao e o unico jeito de liberar o quiz. Nao ha scroll, nao ha
progresso, nao ha "vc ja leu o suficiente": o aluno le e aperta. O
registro do que foi lido fica no banco (tabela "leituras"), por aluno e
por modulo, entao a liberacao do quiz sobrevive a fechar o navegador.
"""

import base64
import html
import os

import streamlit as st

from modules.database import (
    registrar_leitura,
    modulo_lido,
)
from modules.estilo import html_bruto
from modules.modulos import PASTA_PDFS, modulo_por_slug, caminho_pdf

# Chave da sessao que diz qual modulo esta em leitura. Enquanto ela
# existir, o app desenha a pagina de leitura.
CHAVE_LEITURA = "leitura_em_curso"


@st.cache_data(ttl=3600, show_spinner=False)
def _ler_pdf_base64(caminho_absoluto, mtime_ns, tamanho):
    stat = os.stat(caminho_absoluto)
    if stat.st_mtime_ns != mtime_ns or stat.st_size != tamanho:
        raise OSError("O PDF mudou durante a leitura. Recarregue a página.")
    with open(caminho_absoluto, "rb") as arquivo:
        return base64.b64encode(arquivo.read()).decode("ascii")


def _pdf_em_base64(modulo):
    """Le e codifica o PDF local para embuti-lo diretamente no iframe."""
    caminho = caminho_pdf(modulo)
    if caminho is None:
        return None, None

    pasta_absoluta = os.path.realpath(PASTA_PDFS)
    caminho_absoluto = os.path.realpath(os.path.abspath(caminho))
    try:
        if os.path.commonpath((pasta_absoluta, caminho_absoluto)) != pasta_absoluta:
            return None, "O caminho do PDF está fora da pasta de materiais."
    except ValueError:
        return None, "O caminho do PDF está fora da pasta de materiais."

    try:
        stat = os.stat(caminho_absoluto)
        pdf_base64 = _ler_pdf_base64(
            caminho_absoluto, stat.st_mtime_ns, stat.st_size
        )
    except OSError as erro:
        return None, "Não consegui ler o PDF: %s" % erro

    return pdf_base64, None


def render_pagina_leitura(slug):
    """Desenha a pagina de leitura de um modulo.

    E o que o app chama quando o aluno aperta "Abrir a pagina de
    leitura". A pagina tem o material, o botao de concluir e o botao
    de voltar sem concluir.
    """
    modulo = modulo_por_slug(slug)
    if modulo is None:
        # O manifesto mudou entre a sessao aberta e agora. Nao derruba
        # o app: volta para o mapa de missoes.
        st.warning("Módulo não encontrado. Voltando para o mapa de missões.")
        st.session_state.pop(CHAVE_LEITURA, None)
        st.rerun()
        return

    titulo = html.escape(modulo.get("titulo", ""))
    icone = html.escape(modulo.get("icone", "📘"))
    resumo = html.escape(modulo.get("resumo", ""))
    cor = html.escape(modulo.get("cor", "#4F46E5"))

    st.markdown(
        html_bruto(
            f"""
            <div class="ce-modulo-cabecalho" style="--ce-cor-modulo: {cor}">
              <h2>{icone} {titulo}</h2>
              <p>{resumo}</p>
              <div class="ce-tags">
                <span class="ce-badge ce-badge-nivel">📖 PÁGINA DE LEITURA</span>
              </div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

    st.write(
        "Leia o material abaixo. Quando terminar, aperte **Concluir a "
        "leitura** para liberar o quiz deste módulo."
    )

    # ---------- O material ----------
    pdf_base64, erro_pdf = _pdf_em_base64(modulo)

    if erro_pdf:
        st.error(erro_pdf)
    elif pdf_base64 is not None:
        # Sem botao de baixar. O botao entregava o arquivo do professor
        # na mao do aluno, e quem tem o arquivo pode edita-lo e
        # redistribuir -- o material do professor saia da pagina dele.
        #
        # O PDF vai no proprio HTML como data URI; assim o iframe nao
        # depende de uma URL local que o navegador da nuvem nao consegue abrir.
        st.markdown(
            html_bruto(
                f"""
                <iframe
                    src="data:application/pdf;base64,{pdf_base64}"
                    width="100%"
                    height="820"
                    style="border:1px solid rgba(148, 163, 184, 0.25);
                           border-radius:12px;
                           background:#1e293b;"
                    title="Material de leitura do módulo">
                </iframe>
                """
            ),
            unsafe_allow_html=True,
        )
    else:
        st.info(
            "Este módulo ainda não tem material em PDF na pasta "
            "`static/modulos/`. Você pode concluir a leitura mesmo assim — "
            "o botão abaixo funciona igual."
        )

    # ---------- Material extra publicado pela coordenação ----------
    # A tabela "conteudos" do banco hoje e a dos exemplos de crime (os
    # pergaminhos), e nao tem mais material por modulo. Quando existir
    # material extra por modulo, e aqui que ele entra.

    st.divider()

    # ---------- Os botoes ----------
    col1, col2 = st.columns(2)

    if col1.button(
        "✅ Concluir a leitura e liberar o quiz",
        key="concluir_leitura",
        type="primary",
        width="stretch",
    ):
        _registrar_e_voltar(slug)

    if col2.button(
        "← Voltar sem concluir",
        key="voltar_sem_concluir",
        width="stretch",
    ):
        st.session_state.pop(CHAVE_LEITURA, None)
        st.rerun()


def _registrar_e_voltar(slug):
    """Registra a leitura no banco e volta para a pagina do modulo.

    O registro e no banco, e nao so na sessao: se o aluno fechar o
    navegador e voltar amanha, o quiz continua liberado. E o que faz a
    leitura valer alguma coisa.
    """
    username = st.session_state.get("username", "")
    if username:
        registrar_leitura(username, slug)

    # A leitura acabou. A pagina do modulo reaparece, com o quiz
    # liberado.
    st.session_state.pop(CHAVE_LEITURA, None)
    st.rerun()


def abrir_leitura(slug):
    """Comeca a leitura de um modulo. Usado pelo botao do modulo."""
    st.session_state[CHAVE_LEITURA] = slug
    st.rerun()


def quiz_liberado(slug):
    """Diz se o aluno ja concluiu a leitura deste modulo.

    A leitura e o que libera o quiz. Um modulo sem leitura registrada
    fica com o quiz bloqueado -- e o aluno ve o porque.
    """
    username = st.session_state.get("username", "")
    if not username:
        return False
    return modulo_lido(username, slug)
