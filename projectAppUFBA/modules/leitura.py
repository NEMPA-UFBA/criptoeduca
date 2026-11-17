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

import html
import os
from urllib.parse import quote

import streamlit as st

from modules.database import (
    carregar_estado_modulos,
    registrar_leitura,
)
from modules.estilo import html_bruto
from modules.modulos import PASTA_PDFS, modulo_por_slug, caminho_pdf

# Chave da sessao que diz qual modulo esta em leitura. Enquanto ela
# existir, o app desenha a pagina de leitura.
CHAVE_LEITURA = "leitura_em_curso"


def _caminho_pdf_seguro(modulo):
    """Devolve o caminho absoluto do PDF, limitado à pasta de materiais."""
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
        if not os.path.isfile(caminho_absoluto):
            return None, "O arquivo PDF não foi encontrado na pasta de materiais."
    except OSError as erro:
        return None, "Não consegui ler o PDF: %s" % erro

    return caminho_absoluto, None


def _url_do_pdf_estatico(caminho_absoluto):
    """Monta a URL pública do PDF servido pela pasta static do Streamlit.

    O visualizador de PDF do componente antigo parava de desenhar as
    páginas em algumas versões do Chrome. O iframe abaixo usa o leitor
    nativo do navegador, que recebe o mesmo arquivo por esta URL.

    O caminho relativo é calculado a partir de PASTA_PDFS, então um PDF
    fora dessa pasta nunca chega aqui: _caminho_pdf_seguro já recusou.
    """
    relativo = os.path.relpath(caminho_absoluto, PASTA_PDFS)
    relativo = relativo.replace(os.sep, "/")
    base = (st.get_option("server.baseUrlPath") or "").rstrip("/")
    return f"{base}/app/static/modulos/{quote(relativo)}"


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

    with st.container(key=f"pagina_leitura_{slug}"):
        _render_conteudo_leitura(modulo, slug, titulo, icone, resumo, cor)


def _render_conteudo_leitura(modulo, slug, titulo, icone, resumo, cor):
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
    caminho_absoluto, erro_pdf = _caminho_pdf_seguro(modulo)

    if erro_pdf:
        st.error(erro_pdf)
    elif caminho_absoluto is not None:
        # Sem botao de baixar. O botao entregava o arquivo do professor
        # na mao do aluno, e quem tem o arquivo pode edita-lo e
        # redistribuir -- o material do professor saia da pagina dele.
        #
        # O PDF vai num iframe apontando para a URL estatica do proprio
        # Streamlit. O leitor nativo do navegador desenha as paginas; o
        # componente streamlit-pdf-viewer ficava com a area em branco no
        # Chrome atual (o PDF.js dele não montava as páginas).
        url_pdf = _url_do_pdf_estatico(caminho_absoluto)
        st.markdown(
            html_bruto(
                f'<iframe src="{html.escape(url_pdf, quote=True)}" '
                'width="100%" height="800" '
                'style="border:0;border-radius:12px;background:#fff;" '
                'title="Material de leitura do módulo"></iframe>'
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

    col1.button(
        "✅ Concluir a leitura e liberar o quiz",
        key=f"concluir_leitura_{slug}",
        type="primary",
        width="stretch",
        on_click=_registrar_e_voltar,
        args=(slug,),
    )

    col2.button(
        "← Voltar sem concluir",
        key=f"voltar_sem_concluir_{slug}",
        width="stretch",
        on_click=_voltar_sem_concluir,
    )


def _voltar_sem_concluir():
    """Fecha a leitura sem registrar nada no banco."""
    st.session_state.pop(CHAVE_LEITURA, None)


def _registrar_e_voltar(slug):
    """Registra a leitura no banco e volta para a pagina do modulo.

    O registro e no banco, e nao so na sessao: se o aluno fechar o
    navegador e voltar amanha, o quiz continua liberado. E o que faz a
    leitura valer alguma coisa.

    Roda como callback do botao. O rerun que redesenha a pagina do
    modulo ja acontece depois do callback, entao nao ha st.rerun aqui.
    """
    username = st.session_state.get("username", "")
    if username:
        registrar_leitura(username, slug)

    # A leitura acabou. A pagina do modulo reaparece, com o quiz
    # liberado.
    st.session_state.pop(CHAVE_LEITURA, None)


def abrir_leitura(slug):
    """Comeca a leitura de um modulo. Usado como callback do botao."""
    st.session_state[CHAVE_LEITURA] = slug


def quiz_liberado(slug):
    """Diz se o aluno ja concluiu a leitura deste modulo.

    A leitura e o que libera o quiz. Um modulo sem leitura registrada
    fica com o quiz bloqueado -- e o aluno ve o porque.

    Usa o mesmo cache de carregar_estado_modulos que a pagina do modulo,
    em vez de uma segunda consulta so para esta resposta.
    """
    username = st.session_state.get("username", "")
    if not username:
        return False
    _, lidos = carregar_estado_modulos(username)
    return slug in lidos
