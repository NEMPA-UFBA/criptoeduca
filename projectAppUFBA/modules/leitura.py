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

import streamlit as st

from modules.database import (
    registrar_leitura,
    modulo_lido,
)
from modules.estilo import html_bruto
from modules.modulos import modulo_por_slug, caminho_pdf, pdf_disponivel

# Chave da sessao que diz qual modulo esta em leitura. Enquanto ela
# existir, o app desenha a pagina de leitura.
CHAVE_LEITURA = "leitura_em_curso"


def _pdf_para_visualizar(modulo):
    """Descobre o PDF do modulo, olhando nos dois lugares possiveis.

    O PDF esta em dois lugares: a pasta static/modulos/ (que e o que o
    app serve ao navegador) e a tabela "conteudos" do banco (que e o
    que a coordenacao publica). O de arquivo vem primeiro, porque e o
    material de leitura do modulo; o do banco e o material extra
    publicado junto.
    """
    if pdf_disponivel(modulo):
        return caminho_pdf(modulo)
    return None


def _url_do_pdf(modulo):
    """URL publica do PDF do modulo, para o <iframe> exibir.

    Os parametros depois do "#" sao do VISUALIZADOR NATIVO do navegador
    (o Chrome, o Edge e o Firefox embedded tem o mesmo), e nao do
    Streamlit:

      toolbar=0   -> esconde a barra de ferramentas. E o que tira do
                      aluno a caneta de ANOTACAO, com que da para
                      "editar" o PDF desenhando por cima. Sem isso, o
                      aluno podia marcar o material do professor.
      navpanes=0  -> esconde o painel de miniaturas.
      view=FitH   -> ajusta a altura da pagina no visor.
    """
    nome = (modulo.get("pdf") or "").rsplit("/", 1)[-1]
    if not nome:
        return None
    return "/app/static/modulos/%s#toolbar=0&navpanes=0&view=FitH" % nome


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
    caminho = _pdf_para_visualizar(modulo)
    url = _url_do_pdf(modulo)

    if url:
        # Sem botao de baixar. O botao entregava o arquivo do professor
        # na mao do aluno, e quem tem o arquivo pode edita-lo e
        # redistribuir -- o material do professor saia da pagina dele.
        #
        # A leitura acontece dentro do app, com o visualizador do
        # navegador em modo somente-leitura (toolbar=0 na URL, ver
        # _url_do_pdf). Sem a barra de ferramentas, some a caneta de
        # anotacao com que da para "editar" o PDF desenhando por cima.
        st.markdown(
            html_bruto(
                f"""
                <iframe
                    src="{html.escape(url)}"
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
