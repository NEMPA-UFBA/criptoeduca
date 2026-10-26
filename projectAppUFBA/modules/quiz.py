"""O quiz do modulo.

O quiz e a parte do modulo que o aluno faz DEPOIS de ler. Ele so aparece
para quem ja concluiu a leitura -- ver modules/leitura.py, que e quem
decide se o quiz esta liberado.

O manifesto (dados/modulos.json) traz as perguntas de cada modulo:
enunciado, lista de alternativas e qual e a certa. Aqui o quiz vira
tela: uma pergunta por vez, com as alternativas, o botao de responder e
o resultado no fim.

O resultado de cada tentativa e gravado em "progresso_modulos", que ja
existe no banco. Cada tentativa vira uma linha: o historico fica, e a
melhor nota e a que a tela usa.

UM DETALHE QUE PARECE DETALHE E NAO E: o resultado SUBSTITUI o
formulario, e nao aparece abaixo dele.

A primeira versao desenhava as perguntas e o gabarito na MESMA tela, e
o gabarito ficava ali enquanto o aluno ainda mexia nas alternativas. O
aluno via a resposta certa de uma pergunta que ele ainda nao tinha
respondido -- e o gabarito aparecia antes de o quiz acabar, que e
exatamente o que nao deve acontecer.

Agora sao dois estados que nao coexistem:

    SEM RESULTADO  ->  as perguntas e o botao "Ver meu resultado"
    COM RESULTADO  ->  a nota, o gabarito e o botao "Tentar de novo"

O gabarito so existe no segundo estado. Para voltar ao primeiro, o
aluno aperta "Tentar de novo", que limpa as respostas marcadas. Nao ha
como o gabarito estar na tela junto com uma pergunta em branco.
"""

import html

import streamlit as st

from modules.database import salvar_progresso_modulo, carregar_progresso_modulos
from modules.estilo import html_bruto

# Chave da sessao que guarda o resultado de uma tentativa, por modulo.
#
# O "%s" e o slug. O valor guardado e o dicionario com as respostas que
# foram enviadas, o numero de acertos e o total.
_CHAVE_RESULTADO = "quiz_resultado_%s"


def _perguntas_do_modulo(modulo):
    """Devolve as perguntas do modulo, ja validadas pelo leitor.

    O leitor (modules/modulos.py) ja descartou as perguntas invalidas e
    ja converteu o indice da resposta certa. Aqui e so a lista.
    """
    return modulo.get("quiz") or []


def _melhor_nota(username, slug):
    """A melhor nota que o aluno ja fez neste modulo, ou None."""
    if not username:
        return None
    progresso = carregar_progresso_modulos(username)
    return progresso.get(slug)


def _limpar_respostas(slug, perguntas):
    """Apaga as alternativas marcadas e o resultado guardado.

    E o que o botao "Tentar de novo" chama. As chaves dos widgets sao
    removidas do session_state para que o proximo quiz comece em
    branco -- sem isso, a alternativa que o aluno tinha marcado voltaria
    ja marcada, e ele acharia que ja tinha respondido.
    """
    st.session_state.pop(_CHAVE_RESULTADO % slug, None)
    for indice in range(1, len(perguntas) + 1):
        st.session_state.pop("quiz_%s_%d" % (slug, indice), None)


def render_quiz(modulo, slug):
    """Desenha o quiz de um modulo.

    Devolve True se o aluno respondeu agora, e False se nao respondeu
    (ou se nao havia quiz). Quem chama usa isso para saber se vale
    mostrar a celebracao.
    """
    perguntas = _perguntas_do_modulo(modulo)
    if not perguntas:
        st.info(
            "Este módulo ainda não tem quiz. O professor pode escrever as "
            "perguntas no arquivo `dados/modulos.json`."
        )
        return False

    username = st.session_state.get("username", "")

    # ---------- A nota anterior ----------
    # Fica no topo: o aluno precisa saber onde esta, e o professor
    # precisa ver que a repeticao nao zera o historico.
    anterior = _melhor_nota(username, slug)
    if anterior:
        st.caption(
            "Sua melhor nota neste módulo: **%d de %d** (%s)."
            % (
                anterior["acertos"],
                anterior["total"],
                anterior["data"],
            )
        )

    st.subheader("🧠 Quiz do módulo")

    # ---------- O resultado ----------
    # Se ha resultado guardado, a tela E o resultado. As perguntas nao
    # sao desenhadas: o gabarito nunca aparece junto com uma pergunta
    # em branco.
    resultado = st.session_state.get(_CHAVE_RESULTADO % slug)

    if resultado:
        _desenhar_resultado(resultado, perguntas, slug)
        return True

    st.write(
        "Responda todas as perguntas e aperte **Ver meu resultado**."
    )

    # ---------- As perguntas ----------
    # Sem st.form, de proposito: dentro de um form, marcar uma
    # alternativa nao re-executa o script, e o estado do widget ficava
    # velho. O comentario no topo do arquivo explica o por.
    #
    # As chaves levam o slug para que dois modulos nao compartilhem a
    # mesma resposta -- o Streamlit reclama de chaves repetidas, e o
    # certo seria o aluno ver a resposta de um modulo no quiz do outro.
    respostas = {}
    for indice, pergunta in enumerate(perguntas, start=1):
        st.markdown(
            html_bruto(
                f"""
                <p class="ce-quiz-enunciado"><strong>{indice}.</strong> {html.escape(pergunta["enunciado"])}</p>
                """
            ),
            unsafe_allow_html=True,
        )
        escolhida = st.radio(
            "Resposta %d" % indice,
            options=list(range(len(pergunta["alternativas"]))),
            format_func=lambda i, alt=pergunta["alternativas"]: alt[i],
            key="quiz_%s_%d" % (slug, indice),
            label_visibility="collapsed",
            # index=None: sem isso o Streamlit marca a PRIMEIRA alternativa
            # como resposta antes de o aluno escolher qualquer coisa. O
            # aluno via a pergunta "respondida" sem ter respondido.
            index=None,
        )
        respostas[indice] = escolhida

    # ---------- O botao ----------
    if st.button(
        "Ver meu resultado",
        key="enviar_quiz_%s" % slug,
        type="primary",
    ):
        # O resultado so e guardado quando TODAS as perguntas tem
        # resposta. Sem isso, "Ver meu resultado" com metade respondida
        # contaria as nao respondidas como erradas, e o aluno levaria
        # uma nota que nao corresponde ao que ele respondeu.
        faltando = [i for i in respostas if respostas[i] is None]
        if faltando:
            st.error(
                "Responda todas as perguntas antes de ver o resultado. "
                "Falta: %s."
                % ", ".join("questão %d" % i for i in faltando)
            )
            return False

        acertos = 0
        for indice, pergunta in enumerate(perguntas, start=1):
            if respostas.get(indice) == pergunta["certa"]:
                acertos += 1

        total = len(perguntas)

        # A tentativa e gravada. O historico de tentativas fica no banco:
        # a tela usa a melhor nota, mas o professor ve todas.
        if username:
            salvar_progresso_modulo(username, slug, acertos, total)

        st.session_state[_CHAVE_RESULTADO % slug] = {
            "respostas": dict(respostas),
            "acertos": acertos,
            "total": total,
        }
        st.rerun()

    return False


def _desenhar_resultado(resultado, perguntas, slug):
    """Desenha a nota e o gabarito de uma tentativa.

    E a tela que substitui as perguntas depois que o aluno envia.
    """
    acertos = resultado["acertos"]
    total = resultado["total"]
    percentual = int(round((acertos / total) * 100)) if total else 0

    st.divider()

    if percentual == 100:
        st.success(
            "🎉 Gabaritou! **%d de %d**. Você domina este módulo."
            % (acertos, total)
        )
    elif percentual >= 60:
        st.warning(
            "Quase lá! **%d de %d** (%d%%). Dá uma olhada de novo no "
            "material das perguntas que você errou."
            % (acertos, total, percentual)
        )
    else:
        st.error(
            "**%d de %d** (%d%%). Vale ler o material de novo e refazer o "
            "quiz — a nota continua melhorando a cada tentativa."
            % (acertos, total, percentual)
        )

    # O gabarito, pergunta por pergunta. Aparece sempre, mesmo quando o
    # aluno gabaritou: quem acertou tambem precisa conferir o
    # raciocinio das outras.
    st.subheader("Gabarito")
    for indice, pergunta in enumerate(perguntas, start=1):
        escolhida = resultado["respostas"].get(indice)
        certa = pergunta["certa"]
        acertou = escolhida == certa

        with st.expander(
            "%s %d. %s" % ("✅" if acertou else "❌", indice, pergunta["enunciado"]),
            expanded=False,
        ):
            st.markdown(
                "**Resposta certa:** %s"
                % html.escape(pergunta["alternativas"][certa])
            )
            if not acertou and escolhida is not None:
                st.markdown(
                    "**A sua resposta:** %s"
                    % html.escape(pergunta["alternativas"][escolhida])
                )

    # "Tentar de novo" volta para as perguntas em branco. Sem ele, o
    # aluno que mudou de ideia ficaria preso no gabarito.
    if st.button(
        "↩️ Tentar de novo",
        key="tentar_de_novo_%s" % slug,
    ):
        _limpar_respostas(slug, perguntas)
        st.rerun()
