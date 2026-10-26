"""Home dos modulos de aprendizagem -- o "Mapa de Missoes".

Esta e a pagina que o item "Modulos de Aprendizado" da barra lateral abre.
Ela nao mostra conteudo de modulo: ela mostra a lista deles, em cards, com o
progresso de quem esta logado. O conteudo de cada modulo vive na pagina
individual (modules/paginaModulo.py), que e aberta a partir do botao do
card.

O arquivo estava vazio e reservado para a continuidade do projeto -- e e
exatamente para isto que ele serve agora.
"""

import html

import streamlit as st

from modules.database import carregar_progresso_modulos
from modules.database import modulos_lidos as modulos_lidos_no_banco
from modules.estilo import aplicar_estilo, html_bruto
from modules.modulos import carregar_modulos

# Quantos cards cabem numa linha. Tres em tela larga, e o CSS encolhe o card
# em tela estreita. O Streamlit nao tem media query para numero de colunas.
COLUNAS = 3


def _html(trecho):
    """Atalho para html_bruto (ver a explicação lá)."""
    return html_bruto(trecho)


def _progresso_do_aluno():
    """Progresso do usuario logado: {slug: {acertos, total, data}}.

    Devolve dicionario vazio para quem nao tem usuario na sessao (o app
    so desenha esta pagina depois do login, mas o mural e o login
    compartilham o mesmo arquivo de sessao -- melhor nao assumir).
    """
    username = st.session_state.get("username")
    if not username:
        return {}
    try:
        return carregar_progresso_modulos(username)
    except Exception:
        # O progresso e enfeite. Se o banco estiver travado, a lista de
        # modulos tem que aparecer mesmo assim.
        return {}


def _modulos_lidos():
    """Conjunto de slugs cujo material o aluno ja terminou de ler.

    E o que libera o quiz. Vem do banco (modules/leitura.py), e nao da
    sessao, porque a leitura precisa sobreviver ao fechamento do
    navegador.
    """
    username = st.session_state.get("username")
    if not username:
        return set()
    try:
        return modulos_lidos_no_banco(username)
    except Exception:
        return set()


def _caixa_progresso(concluidos, total):
    """Barra de progresso dos modulos, em HTML."""
    if total <= 0:
        return ""
    porcentagem = int(round((concluidos / total) * 100))
    return _html(
        f"""
        <div class="ce-progresso-caixa">
          <div class="ce-progresso-topo">
            <span class="ce-progresso-titulo">🗺️ Sua jornada</span>
            <span class="ce-progresso-fracao">{concluidos} de {total} módulo(s) concluído(s) · {porcentagem}%</span>
          </div>
          <div class="ce-progresso-trilho">
            <div class="ce-progresso-barra" style="width: {porcentagem}%"></div>
          </div>
        </div>
        """
    )


def _card_html(modulo, concluido, lido=False):
    """Markdown do card de um modulo.

    O conteudo vem do manifesto (modules/modulos.py), e nao de digitacao
    solta no HTML. Ainda assim ele passa por html.escape: o titulo e o
    resumo entram no HTML cru, e um texto com "<" no meio abriria tag sem
    querer.

    Os dois selos sao coisas diferentes:

      "Lido"       -> o aluno terminou o material. E o que libera o quiz.
      "Concluído" -> o aluno respondeu o quiz e teve acerto.
    """
    icone = html.escape(modulo.get("icone", "📘"))
    titulo = html.escape(modulo.get("titulo", ""))
    resumo = html.escape(modulo.get("resumo", ""))
    nivel = html.escape(modulo.get("nivel", ""))
    dificuldade = html.escape(modulo.get("dificuldade", ""))
    duracao = html.escape(modulo.get("duracao", ""))
    cor = html.escape(modulo.get("cor", "#4F46E5"))

    badge_ok = (
        '<span class="ce-badge ce-badge-ok">✔ Concluído</span>' if concluido else ""
    )
    badge_lido = (
        '<span class="ce-badge ce-badge-lido">📖 Lido</span>' if lido else ""
    )

    return _html(
        f"""
        <div class="ce-card" style="--ce-cor-modulo: {cor}">
          <div class="ce-card-topo">
            <span class="ce-icone" style="background: {cor}22; border-color: {cor}66;">{icone}</span>
            <span class="ce-badge ce-badge-nivel">{nivel}</span>
          </div>
          <p class="ce-titulo">{titulo}</p>
          <p class="ce-resumo">{resumo}</p>
          <div class="ce-tags">
            <span class="ce-badge">📖 {dificuldade}</span>
            <span class="ce-badge">⏱️ {duracao}</span>
            {badge_lido}
            {badge_ok}
          </div>
        </div>
        """
    )


def render_modulos():
    """Desenha a pagina-índice dos modulos."""
    aplicar_estilo()

    st.markdown(
        _html(
            """
            <p class="ce-pixel">MAPA DE MISSÕES</p>
            <p class="ce-subtitulo">Escolha um módulo para estudar. Cada um tem material de leitura e um quiz para você checar o que aprendeu.</p>
            """
        ),
        unsafe_allow_html=True,
    )

    modulos, erros = carregar_modulos()

    if erros:
        # O arquivo dados/modulos.json foi editado por alguém e tem
        # alguma coisa errada. Isso nao pode derrubar a tela: o app
        # explica o que precisa ser corrigido e mostra os modulos que
        # deu para ler.
        with st.expander(
            f"⚠️ {len(erros)} problema(s) no arquivo de módulos "
            "(dados/modulos.json)",
            expanded=True,
        ):
            st.write(
                "O app continua funcionando com os módulos que puderam ser "
                "lidos. Para corrigir, edite o arquivo "
                "`dados/modulos.json` e recarregue a página (F5)."
            )
            for erro in erros:
                st.error(erro)

    if not modulos:
        st.info(
            "Nenhum módulo cadastrado ainda. Os módulos são declarados no "
            "arquivo `dados/modulos.json`."
        )
        return

    progresso = _progresso_do_aluno()
    lidos = _modulos_lidos()
    concluidos = sum(1 for m in modulos if m["slug"] in progresso)
    st.markdown(
        _caixa_progresso(concluidos, len(modulos)), unsafe_allow_html=True
    )

    for linha_inicio in range(0, len(modulos), COLUNAS):
        trecho = modulos[linha_inicio : linha_inicio + COLUNAS]
        colunas = st.columns(COLUNAS)

        for coluna, modulo in zip(colunas, trecho):
            with coluna:
                slug = modulo["slug"]
                # Sem altura fixa: com height=420 o card ficava do tamanho
                # fixo, mas o conteúdo passava da altura e aparecia uma
                # barra de rolagem dentro do card -- medido, cards de 443px
                # a 509px de conteúdo dentro de uma caixa de 420px. A
                # igualdade de altura vem do min-height do CSS, e não de
                # cortar o texto.
                #
                # A key= não é decorativa: é ela que dá a classe
                # "st-key-card_<slug>" no HTML, e o CSS usa essa classe para
                # esticar o conteúdo na largura da coluna.
                with st.container(key=f"card_{slug}"):
                    st.markdown(
                        _card_html(modulo, slug in progresso, slug in lidos),
                        unsafe_allow_html=True,
                    )
                    if st.button(
                        "Iniciar módulo →",
                        key=f"iniciar_modulo_{slug}",
                        type="primary",
                        width="stretch",
                    ):
                        st.session_state["modulo_selecionado"] = slug
                        st.rerun()


def render_progresso_aluno():
    """Desenha a pagina "Meu Progresso".

    Mostra o que o aluno ja fez de verdade: quais materiais ele
    terminou de ler (o que libera o quiz) e qual foi a melhor nota de
    cada quiz. Tudo sai do banco, e nao de um texto de exemplo.

    A pagina esta numa funcao e nao no app.py porque o app.py e um
    script do Streamlit, rodado no nivel do modulo: um "return" la
    dentro quebra o script inteiro (SyntaxError: 'return' outside
    function), e o app inteiro sai do ar.
    """
    aplicar_estilo()

    st.title("📊 Desempenho")
    st.write("O que você já leu e as suas notas nos quizzes.")

    username = st.session_state.get("username", "")
    lidos = _modulos_lidos()
    progresso = _progresso_do_aluno()

    modulos, _erros = carregar_modulos()
    if not modulos:
        st.info("Nenhum módulo cadastrado ainda.")
        return

    if not lidos and not progresso:
        st.info(
            "Você ainda não começou nenhum módulo. Abra "
            "**Módulos de Aprendizado** no menu ao lado para começar."
        )

    for modulo in modulos:
        slug = modulo["slug"]
        lido = slug in lidos
        nota = progresso.get(slug)

        with st.expander(
            "%s %s" % (modulo.get("icone", "📘"), modulo.get("titulo", "")),
            expanded=False,
        ):
            if lido:
                st.success("✅ Leitura concluída — quiz liberado.")
            else:
                st.info("🔒 Leitura pendente — o quiz ainda está bloqueado.")

            if nota:
                st.write(
                    "**Melhor nota:** %d de %d (%s)."
                    % (nota["acertos"], nota["total"], nota["data"])
                )
            else:
                st.caption("Nenhuma tentativa de quiz ainda.")
