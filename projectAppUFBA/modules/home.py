"""Painel inicial do CriptoEduca.

A primeira página de cada perfil era só um título e uma frase. Esta home
reúne, a partir dos dados que o app já grava, o que a pessoa precisa ver
primeiro:

  - Aluno: quanto do mapa já foi concluído, qual é o próximo passo e os
    últimos resultados dos quizzes.
  - Professor: o movimento recente da turma, os números da plataforma e os
    atalhos para as ferramentas de conteúdo.
  - Administrador: a visão geral das contas e dos conteúdos, os mesmos
    atalhos do professor e a chave diária de credenciamento.

Nada aqui é número de exemplo: tudo sai do banco ou do manifesto de módulos.
"""

import html
import logging
from datetime import datetime

import streamlit as st

from modules.database import (
    carregar_estado_modulos,
    carregar_mural,
    carregar_pergaminhos,
    contar_usuarios_por_tipo,
    listar_progresso_recente,
)
from modules.estilo import aplicar_estilo, html_bruto
from modules.leitura import CHAVE_LEITURA
from modules.login import obter_chave_professor_diaria, segredo_da_chave_configurado
from modules.modulos import carregar_modulos

logger = logging.getLogger(__name__)

CSS_HOME = """
<style>
.ce-home-hero {
    position: relative;
    overflow: hidden;
    border: 1px solid rgba(79, 70, 229, 0.35);
    border-radius: 20px;
    background:
        radial-gradient(circle at 12% 0%, rgba(56, 189, 248, 0.18), transparent 34%),
        linear-gradient(135deg, rgba(79, 70, 229, 0.30), rgba(15, 23, 42, 0.96));
    padding: 1.35rem 1.4rem 1.25rem;
    margin-bottom: 1rem;
}
.ce-home-hero::after {
    content: "";
    position: absolute;
    right: -55px;
    top: -70px;
    width: 190px;
    height: 190px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(56, 189, 248, 0.20), transparent 70%);
    pointer-events: none;
}
.ce-home-hero-linha {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    flex-wrap: wrap;
    margin-bottom: 0.55rem;
}
.ce-home-eyebrow {
    font-family: "PressStart2P", monospace;
    font-size: 8px;
    letter-spacing: 0;
    -webkit-font-smoothing: none;
    color: #7dd3fc;
    text-transform: uppercase;
}
.stMarkdown p.ce-home-saudacao {
    color: #f8fafc;
    font-size: clamp(1.35rem, 2.4vw, 1.9rem);
    font-weight: 800;
    line-height: 1.2;
    margin: 0 0 0.4rem;
}
.stMarkdown p.ce-home-descricao {
    color: #cbd5e1;
    font-size: 0.95rem;
    line-height: 1.55;
    margin: 0;
    max-width: 72ch;
}
.stMarkdown p.ce-home-data {
    color: #94a3b8;
    font-size: 0.78rem;
    margin: 0.55rem 0 0;
}
.ce-home-stats {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.75rem;
    margin: 0.9rem 0 1.1rem;
}
.ce-home-stat {
    display: flex;
    flex-direction: column;
    gap: 0.22rem;
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: 14px;
    background: linear-gradient(160deg, rgba(30, 41, 59, 0.92), rgba(15, 23, 42, 0.94));
    padding: 0.85rem 0.95rem;
    min-width: 0;
}
.ce-home-stat-icone {
    font-size: 1.15rem;
    line-height: 1;
    margin-bottom: 0.15rem;
}
.ce-home-stat-valor {
    color: #f8fafc;
    font-size: 1.45rem;
    font-weight: 800;
    line-height: 1.1;
    overflow-wrap: anywhere;
}
.ce-home-stat-rotulo {
    color: #cbd5e1;
    font-size: 0.78rem;
    font-weight: 600;
    line-height: 1.3;
}
.ce-home-stat-detalhe {
    color: #94a3b8;
    font-size: 0.72rem;
    line-height: 1.35;
    margin-top: 0.1rem;
}
.stMarkdown p.ce-home-secao-titulo {
    color: #f1f5f9;
    font-size: 1.05rem;
    font-weight: 800;
    line-height: 1.3;
    margin: 0 0 0.65rem;
}
.stMarkdown p.ce-home-secao-titulo.ce-home-secundaria {
    margin-top: 1.35rem;
    font-size: 0.95rem;
    color: #cbd5e1;
}
.ce-home-destaque {
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-left: 4px solid var(--ce-cor-modulo, #4F46E5);
    border-radius: 14px;
    background: linear-gradient(160deg, rgba(30, 41, 59, 0.94), rgba(15, 23, 42, 0.96));
    padding: 1rem 1.1rem;
    margin-bottom: 0.8rem;
}
.ce-home-destaque-topo {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.75rem;
    margin-bottom: 0.65rem;
}
.ce-home-destaque-icone {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2.8rem;
    height: 2.8rem;
    border-radius: 12px;
    background: rgba(79, 70, 229, 0.16);
    border: 1px solid rgba(79, 70, 229, 0.35);
    font-size: 1.35rem;
    line-height: 1;
    flex-shrink: 0;
}
.ce-home-destaque-meta {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 0.35rem;
}
.stMarkdown p.ce-home-destaque-titulo {
    color: #f8fafc;
    font-size: 1.15rem;
    font-weight: 800;
    line-height: 1.3;
    margin: 0 0 0.3rem;
}
.stMarkdown p.ce-home-destaque-resumo {
    color: #cbd5e1;
    font-size: 0.9rem;
    line-height: 1.55;
    margin: 0 0 0.55rem;
}
.stMarkdown p.ce-home-destaque-status {
    color: #7dd3fc;
    font-size: 0.82rem;
    font-weight: 600;
    line-height: 1.45;
    margin: 0;
}
.ce-home-lista {
    display: flex;
    flex-direction: column;
    gap: 0.45rem;
}
.ce-home-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    border: 1px solid rgba(148, 163, 184, 0.14);
    border-radius: 11px;
    background: rgba(30, 41, 59, 0.55);
    padding: 0.65rem 0.75rem;
    min-width: 0;
}
.ce-home-item-principal {
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
    min-width: 0;
}
.ce-home-item-titulo {
    color: #f1f5f9;
    font-size: 0.86rem;
    font-weight: 700;
    line-height: 1.35;
    overflow-wrap: anywhere;
}
.ce-home-item-detalhe {
    color: #94a3b8;
    font-size: 0.74rem;
    line-height: 1.35;
}
.ce-home-item-lado {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 0.15rem;
    flex-shrink: 0;
}
.ce-home-nota {
    display: inline-block;
    border-radius: 999px;
    padding: 0.12rem 0.48rem;
    font-size: 0.72rem;
    font-weight: 800;
    line-height: 1.3;
    white-space: nowrap;
}
.ce-home-nota-ok {
    background: rgba(34, 197, 94, 0.14);
    border: 1px solid rgba(34, 197, 94, 0.35);
    color: #86efac;
}
.ce-home-nota-media {
    background: rgba(245, 158, 11, 0.14);
    border: 1px solid rgba(245, 158, 11, 0.35);
    color: #fcd34d;
}
.ce-home-nota-baixa {
    background: rgba(239, 68, 68, 0.14);
    border: 1px solid rgba(239, 68, 68, 0.35);
    color: #fca5a5;
}
.ce-home-item-data {
    color: #64748b;
    font-size: 0.68rem;
    white-space: nowrap;
}
.stMarkdown p.ce-home-vazio {
    color: #94a3b8;
    font-size: 0.86rem;
    line-height: 1.5;
    margin: 0;
}
@media (max-width: 900px) {
    .ce-home-stats {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
}
@media (max-width: 480px) {
    .ce-home-hero {
        padding: 1.1rem 1rem;
    }
    .ce-home-stats {
        grid-template-columns: 1fr;
    }
    .ce-home-item {
        align-items: flex-start;
    }
    .ce-home-item-lado {
        align-items: flex-end;
    }
}
</style>
"""


def _html(trecho):
    return html_bruto(trecho)


def _plural(quantidade, singular, plural):
    return "%d %s" % (quantidade, singular if quantidade == 1 else plural)


def _saudacao():
    hora = datetime.now().hour
    if hora < 12:
        return "Bom dia"
    if hora < 18:
        return "Boa tarde"
    return "Boa noite"


def _data_curta(valor):
    if not valor:
        return ""
    if hasattr(valor, "strftime"):
        return valor.strftime("%d/%m/%Y")
    return str(valor)[:10]


def _ir_para(pagina):
    st.session_state["navegar_para"] = pagina


def _abrir_catalogo():
    st.session_state.pop("modulo_selecionado", None)
    st.session_state.pop(CHAVE_LEITURA, None)
    st.session_state["navegar_para"] = "Módulos de Aprendizado"


def _abrir_modulo(slug, etapa):
    """Abre o próximo passo do módulo no rerun seguinte.

    A leitura abre direto no material; o quiz abre na página do módulo, com a
    leitura já concluída. O app aplica "navegar_para" antes de desenhar o
    menu lateral, então o clique não esbarra no widget já criado.
    """
    st.session_state["modulo_selecionado"] = slug
    if etapa == "leitura":
        st.session_state[CHAVE_LEITURA] = slug
    else:
        st.session_state.pop(CHAVE_LEITURA, None)
    st.session_state["navegar_para"] = "Módulos de Aprendizado"


def _carregar_modulos():
    try:
        return carregar_modulos()
    except Exception:
        logger.exception("Falha ao carregar os módulos na home")
        st.warning("Não consegui carregar os módulos agora. Tente recarregar a página.")
        return [], []


def _estado_do_aluno():
    username = st.session_state.get("username")
    if not username:
        return {}, set()
    try:
        return carregar_estado_modulos(username)
    except Exception:
        logger.exception("Falha ao carregar o progresso do aluno na home")
        st.warning("Não consegui carregar seu progresso agora.")
        return {}, set()


def _mensagens_do_mural():
    try:
        return carregar_mural()
    except Exception:
        logger.exception("Falha ao carregar o mural na home")
        return []


def _exemplos_de_golpe():
    try:
        return carregar_pergaminhos()
    except Exception:
        logger.exception("Falha ao carregar os exemplos de golpe na home")
        return []


def _usuarios_por_tipo():
    try:
        return contar_usuarios_por_tipo()
    except Exception:
        logger.exception("Falha ao contar usuários na home")
        return {}


def _progresso_recente():
    try:
        return listar_progresso_recente(5)
    except Exception:
        logger.exception("Falha ao carregar as tentativas recentes na home")
        return []


def _hero(tipo):
    nome = st.session_state.get("nome_usuario") or st.session_state.get("username") or "estudante"
    nome = html.escape(str(nome))
    rotulo = {
        "Administrador": "PAINEL DA COORDENAÇÃO",
        "Professor": "PAINEL GERAL",
    }.get(tipo, "PAINEL PRINCIPAL")
    descricao = {
        "Administrador": (
            "Visão geral das contas e dos conteúdos da plataforma. "
            "Use os atalhos para cuidar do material, do mural e das notas."
        ),
        "Professor": (
            "Acompanhe o movimento da turma, os conteúdos publicados e o que "
            "os alunos já responderam nos quizzes."
        ),
    }.get(
        tipo,
        "Seu próximo passo está aqui. Continue de onde parou e avance no mapa "
        "de missões do CriptoEduca.",
    )
    st.markdown(
        _html(
            f"""
            <div class="ce-home-hero">
              <div class="ce-home-hero-linha">
                <span class="ce-home-eyebrow">{rotulo}</span>
                <span class="ce-badge">{html.escape(tipo)}</span>
              </div>
              <p class="ce-home-saudacao">{_saudacao()}, {nome}!</p>
              <p class="ce-home-descricao">{descricao}</p>
              <p class="ce-home-data">{datetime.now().strftime('%d/%m/%Y')}</p>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )


def _stat(icone, valor, rotulo, detalhe=""):
    detalhe_html = (
        '<span class="ce-home-stat-detalhe">%s</span>' % html.escape(detalhe)
        if detalhe
        else ""
    )
    return _html(
        f"""
        <div class="ce-home-stat">
          <span class="ce-home-stat-icone">{html.escape(icone)}</span>
          <span class="ce-home-stat-valor">{html.escape(str(valor))}</span>
          <span class="ce-home-stat-rotulo">{html.escape(rotulo)}</span>
          {detalhe_html}
        </div>
        """
    )


def _render_stats_aluno(modulos, progresso, lidos, mensagens):
    slugs = {modulo["slug"] for modulo in modulos}
    total = len(modulos)
    concluidos = len(set(progresso) & slugs)
    lidos_validos = len(set(lidos) & slugs)
    notas = [
        progresso[slug]["acertos"] / progresso[slug]["total"] * 100
        for slug in slugs & set(progresso)
        if progresso[slug].get("total")
    ]
    media = round(sum(notas) / len(notas)) if notas else None
    percentual = round((concluidos / total) * 100) if total else 0

    cards = [
        _stat(
            "✅",
            "%d/%d" % (concluidos, total) if total else "—",
            "Módulos concluídos",
            "%d%% do mapa" % percentual if total else "Nenhum módulo publicado",
        ),
        _stat(
            "📖",
            "%d/%d" % (lidos_validos, total) if total else "—",
            "Materiais lidos",
            "A leitura libera o quiz",
        ),
        _stat(
            "🧠",
            "%d%%" % media if media is not None else "—",
            "Média nos quizzes",
            _plural(len(notas), "quiz respondido", "quizzes respondidos")
            if notas
            else "Responda um quiz para ver",
        ),
        _stat(
            "💬",
            len(mensagens),
            "Mural de Criptografia",
            _plural(len(mensagens), "mensagem ativa", "mensagens ativas"),
        ),
    ]
    st.markdown('<div class="ce-home-stats">%s</div>' % "".join(cards), unsafe_allow_html=True)


def _render_stats_staff(tipo, modulos, mensagens, exemplos):
    usuarios = _usuarios_por_tipo()
    total_usuarios = sum(usuarios.values())
    alunos = usuarios.get("Aluno", 0)
    professores = usuarios.get("Professor", 0)
    categorias = len({modulo.get("categoria") for modulo in modulos if modulo.get("categoria")})

    if tipo == "Administrador":
        cards = [
            _stat(
                "👥",
                total_usuarios,
                "Usuários cadastrados",
                "%s · %s" % (
                    _plural(alunos, "aluno", "alunos"),
                    _plural(professores, "professor", "professores"),
                ),
            ),
            _stat(
                "🗺️",
                len(modulos),
                "Módulos disponíveis",
                _plural(categorias, "categoria", "categorias"),
            ),
            _stat(
                "💬",
                len(mensagens),
                "Mensagens no mural",
                _plural(len(mensagens), "mensagem ativa", "mensagens ativas"),
            ),
            _stat(
                "🧾",
                len(exemplos),
                "Exemplos de golpe",
                "Conteúdos publicados",
            ),
        ]
    else:
        cards = [
            _stat(
                "👥",
                alunos,
                "Alunos na plataforma",
                _plural(alunos, "aluno cadastrado", "alunos cadastrados"),
            ),
            _stat(
                "🗺️",
                len(modulos),
                "Módulos disponíveis",
                _plural(categorias, "categoria", "categorias"),
            ),
            _stat(
                "💬",
                len(mensagens),
                "Mensagens no mural",
                _plural(len(mensagens), "mensagem ativa", "mensagens ativas"),
            ),
            _stat(
                "🧾",
                len(exemplos),
                "Exemplos de golpe",
                "Conteúdos publicados",
            ),
        ]

    st.markdown('<div class="ce-home-stats">%s</div>' % "".join(cards), unsafe_allow_html=True)


def _barra_progresso(concluidos, total):
    if total <= 0:
        return ""
    percentual = int(round((concluidos / total) * 100))
    return _html(
        f"""
        <div class="ce-progresso-caixa">
          <div class="ce-progresso-topo">
            <span class="ce-progresso-titulo">🗺️ Sua jornada</span>
            <span class="ce-progresso-fracao">{concluidos} de {total} módulo(s) concluído(s) · {percentual}%</span>
          </div>
          <div class="ce-progresso-trilho">
            <div class="ce-progresso-barra" style="width: {percentual}%"></div>
          </div>
        </div>
        """
    )


def _proximo_passo(modulos, progresso, lidos):
    pendentes = [modulo for modulo in modulos if modulo["slug"] not in progresso]
    for modulo in pendentes:
        if modulo["slug"] in lidos:
            return modulo, "quiz"
    return (pendentes[0], "leitura") if pendentes else (None, None)


def _secao_continuar(modulos, progresso, lidos):
    st.markdown(
        '<p class="ce-home-secao-titulo">🚀 Continue de onde parou</p>',
        unsafe_allow_html=True,
    )

    if not modulos:
        st.info("Nenhum módulo publicado ainda. Volte quando a coordenação liberar o material.")
        return

    modulo, etapa = _proximo_passo(modulos, progresso, lidos)
    if not modulo:
        st.success(
            "Você concluiu todos os módulos disponíveis. Pode revisar o "
            "material ou refazer os quizzes quando quiser."
        )
        st.button(
            "🗺️ Revisar módulos",
            key="home_revisar_modulos",
            type="primary",
            width="stretch",
            on_click=_abrir_catalogo,
        )
        return

    icone = html.escape(modulo.get("icone", "📘"))
    titulo = html.escape(modulo.get("titulo", ""))
    resumo = html.escape(modulo.get("resumo", ""))
    cor = html.escape(modulo.get("cor", "#4F46E5"))
    categoria = html.escape(modulo.get("categoria", ""))
    duracao = html.escape(modulo.get("duracao", ""))
    nivel = html.escape(modulo.get("nivel", ""))

    if etapa == "quiz":
        status = "🧠 Você já leu este material — o quiz está liberado."
        rotulo = "Responder ao quiz →"
        etapa_botao = "quiz"
    else:
        status = "📖 Comece pela leitura. O quiz libera quando você terminar."
        rotulo = "Começar a leitura →"
        etapa_botao = "leitura"

    st.markdown(
        _html(
            f"""
            <div class="ce-home-destaque" style="--ce-cor-modulo: {cor}">
              <div class="ce-home-destaque-topo">
                <span class="ce-home-destaque-icone" style="background: {cor}22; border-color: {cor}66;">{icone}</span>
                <div class="ce-home-destaque-meta">
                  <span class="ce-badge">{categoria}</span>
                  <span class="ce-badge ce-badge-nivel">{nivel}</span>
                  <span class="ce-badge">⏱️ {duracao}</span>
                </div>
              </div>
              <p class="ce-home-destaque-titulo">{titulo}</p>
              <p class="ce-home-destaque-resumo">{resumo}</p>
              <p class="ce-home-destaque-status">{status}</p>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )
    st.button(
        rotulo,
        key="home_continuar_%s" % modulo["slug"],
        type="primary",
        width="stretch",
        on_click=_abrir_modulo,
        args=(modulo["slug"], etapa_botao),
    )


def _classe_da_nota(percentual):
    if percentual >= 70:
        return "ce-home-nota-ok"
    if percentual >= 50:
        return "ce-home-nota-media"
    return "ce-home-nota-baixa"


def _secao_resultados(modulos, progresso):
    st.markdown(
        '<p class="ce-home-secao-titulo ce-home-secundaria">📊 Seus últimos resultados</p>',
        unsafe_allow_html=True,
    )

    itens = []
    for modulo in modulos:
        nota = progresso.get(modulo["slug"])
        if nota:
            itens.append((nota.get("data"), modulo, nota))
    itens.sort(key=lambda item: str(item[0] or ""), reverse=True)

    if not itens:
        st.markdown(
            '<p class="ce-home-vazio">Nenhuma tentativa de quiz ainda. '
            "Quando você responder, o resultado aparece aqui.</p>",
            unsafe_allow_html=True,
        )
        return

    linhas = []
    for data, modulo, nota in itens[:4]:
        total = nota.get("total") or 0
        acertos = nota.get("acertos") or 0
        percentual = round((acertos / total) * 100) if total else 0
        linhas.append(
            _html(
                f"""
                <div class="ce-home-item">
                  <div class="ce-home-item-principal">
                    <span class="ce-home-item-titulo">{html.escape(modulo.get('icone', '📘'))} {html.escape(modulo.get('titulo', ''))}</span>
                    <span class="ce-home-item-detalhe">{acertos} de {total} acerto(s)</span>
                  </div>
                  <div class="ce-home-item-lado">
                    <span class="ce-home-nota {_classe_da_nota(percentual)}">{percentual}%</span>
                    <span class="ce-home-item-data">{html.escape(_data_curta(data))}</span>
                  </div>
                </div>
                """
            )
        )
    st.markdown('<div class="ce-home-lista">%s</div>' % "".join(linhas), unsafe_allow_html=True)


def _secao_atividade(modulos, mensagens):
    st.markdown(
        '<p class="ce-home-secao-titulo">🕒 Atividade recente</p>',
        unsafe_allow_html=True,
    )

    titulos = {modulo["slug"]: modulo.get("titulo", modulo["slug"]) for modulo in modulos}
    recentes = _progresso_recente()
    if recentes:
        linhas = []
        for _username, nome, slug, acertos, total, data in recentes:
            percentual = round((acertos / total) * 100) if total else 0
            linhas.append(
                _html(
                    f"""
                    <div class="ce-home-item">
                      <div class="ce-home-item-principal">
                        <span class="ce-home-item-titulo">{html.escape(str(nome))}</span>
                        <span class="ce-home-item-detalhe">{html.escape(str(titulos.get(slug, slug)))} · {acertos} de {total}</span>
                      </div>
                      <div class="ce-home-item-lado">
                        <span class="ce-home-nota {_classe_da_nota(percentual)}">{percentual}%</span>
                        <span class="ce-home-item-data">{html.escape(_data_curta(data))}</span>
                      </div>
                    </div>
                    """
                )
            )
        st.markdown('<div class="ce-home-lista">%s</div>' % "".join(linhas), unsafe_allow_html=True)
    else:
        st.markdown(
            '<p class="ce-home-vazio">Nenhuma tentativa de quiz registrada ainda.</p>',
            unsafe_allow_html=True,
        )

    st.markdown(
        '<p class="ce-home-secao-titulo ce-home-secundaria">💬 Movimento no mural</p>',
        unsafe_allow_html=True,
    )
    if mensagens:
        linhas = []
        for _msg_id, username, _texto, data in mensagens[:4]:
            linhas.append(
                _html(
                    f"""
                    <div class="ce-home-item">
                      <div class="ce-home-item-principal">
                        <span class="ce-home-item-titulo">{html.escape(str(username))}</span>
                        <span class="ce-home-item-detalhe">publicou uma mensagem no mural</span>
                      </div>
                      <div class="ce-home-item-lado">
                        <span class="ce-home-item-data">{html.escape(_data_curta(data))}</span>
                      </div>
                    </div>
                    """
                )
            )
        st.markdown('<div class="ce-home-lista">%s</div>' % "".join(linhas), unsafe_allow_html=True)
    else:
        st.markdown(
            '<p class="ce-home-vazio">O mural ainda não tem mensagens ativas.</p>',
            unsafe_allow_html=True,
        )


def _secao_atalhos(tipo):
    st.markdown(
        '<p class="ce-home-secao-titulo">⚡ Atalhos rápidos</p>',
        unsafe_allow_html=True,
    )

    if tipo == "Aluno":
        acoes = [
            ("🗺️", "Todos os módulos", _abrir_catalogo, ()),
            ("💬", "Mural de Criptografia", _ir_para, ("Mural de Criptografia",)),
            ("📊", "Meu Progresso", _ir_para, ("Meu Progresso",)),
            ("🧾", "Exemplos de Crimes Digitais", _ir_para, ("Exemplos de Crimes Digitais",)),
        ]
    else:
        acoes = [
            ("🗂️", "Gerenciar Conteúdos", _ir_para, ("Gerenciar Conteúdos",)),
            ("🧮", "Notas dos Alunos", _ir_para, ("Notas dos Alunos",)),
            ("💬", "Mural de Criptografia", _ir_para, ("Mural de Criptografia",)),
            ("🗺️", "Módulos de Aprendizado", _abrir_catalogo, ()),
        ]

    for indice, (icone, rotulo, callback, args) in enumerate(acoes):
        st.button(
            "%s %s" % (icone, rotulo),
            key="home_atalho_%d" % indice,
            width="stretch",
            on_click=callback,
            args=args,
        )


def _secao_chave_professor():
    st.divider()
    st.subheader("🔑 Chave de acesso para novos professores")
    st.info("Passe este código para os professores que forem se cadastrar hoje:")
    st.code(obter_chave_professor_diaria(), language="text")
    st.caption("Esta chave expira automaticamente às 23:59:59 de hoje.")

    if not segredo_da_chave_configurado():
        st.warning(
            "Esta chave está sendo derivada do segredo padrão que vem no "
            "código-fonte. Ela tem 12 caracteres e é muito difícil de adivinhar, "
            "mas qualquer pessoa com uma cópia do repositório consegue calcular "
            "a chave do dia. Para fechar isso, crie "
            "`.streamlit/secrets.toml` com `CHAVE_SEGREDO = \"...\"` "
            "(esse caminho já está no .gitignore) e reinicie o app. "
            "Esta mensagem some sozinha quando o segredo estiver configurado.",
            icon="⚠️",
        )


def _render_home(tipo):
    modulos, erros = _carregar_modulos()
    mensagens = _mensagens_do_mural()

    _hero(tipo)

    if erros:
        with st.expander(
            "⚠️ %d problema(s) no arquivo de módulos (dados/modulos.json)"
            % len(erros),
            expanded=False,
        ):
            st.write(
                "O app continua funcionando com os módulos que puderam ser "
                "lidos. Para corrigir, edite `dados/modulos.json` e recarregue "
                "a página."
            )
            for erro in erros:
                st.error(erro)

    if tipo == "Aluno":
        progresso, lidos = _estado_do_aluno()
        _render_stats_aluno(modulos, progresso, lidos, mensagens)

        slugs = {modulo["slug"] for modulo in modulos}
        concluidos = len(set(progresso) & slugs)
        if modulos:
            st.markdown(
                _barra_progresso(concluidos, len(modulos)),
                unsafe_allow_html=True,
            )

        coluna_principal, coluna_lateral = st.columns([1.55, 1], gap="large")
        with coluna_principal:
            _secao_continuar(modulos, progresso, lidos)
            _secao_resultados(modulos, progresso)
        with coluna_lateral:
            _secao_atalhos(tipo)
    else:
        exemplos = _exemplos_de_golpe()
        _render_stats_staff(tipo, modulos, mensagens, exemplos)

        coluna_principal, coluna_lateral = st.columns([1.55, 1], gap="large")
        with coluna_principal:
            _secao_atividade(modulos, mensagens)
        with coluna_lateral:
            _secao_atalhos(tipo)

        if tipo == "Administrador":
            _secao_chave_professor()


def render_home():
    """Desenha a home do perfil logado."""
    aplicar_estilo()
    st.markdown(CSS_HOME, unsafe_allow_html=True)
    tipo = st.session_state.get("tipo_usuario") or "Aluno"
    with st.container(key="pagina_home"):
        _render_home(tipo)
