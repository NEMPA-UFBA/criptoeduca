"""Gerenciamento dos modulos de aprendizagem.

Os modulos originais continuam em dados/modulos.json. Os novos sao
gravados na tabela "modulos" do banco, com o autor. A regra de acesso e
simples: quem criou o modulo pode editar e excluir o proprio; o
Administrador pode tudo.

O quiz e editado no formato interno do app (a resposta certa e um indice
contando de 0). Quando o modulo vem do JSON, a gravacao converte de volta
para o formato do arquivo, em que a resposta certa conta de 1.
"""

import os

import streamlit as st

from modules.database import (
    atualizar_modulo,
    excluir_modulo,
    salvar_modulo,
)
from modules.estilo import aplicar_estilo, html_bruto
from modules.mainmenu import _card_html
from modules.modulos import (
    PASTA_PDFS,
    RE_SLUG,
    atualizar_modulo_json,
    carregar_modulos,
    excluir_modulo_json,
    gerar_slug,
)

MAX_PERGUNTAS = 20

# Limite do material em PDF. O st.file_uploader barra o arquivo grande no
# navegador (max_upload_size), e _salvar_pdf confere de novo no servidor:
# a checagem do widget e do cliente, e nao deve ser a unica barreira.
MAX_PDF_MB = 20

# Chave da sessao que diz se o formulario de criacao esta aberto. Fica em
# uma chave propria porque o "expanded" do st.expander nao e um widget: ele
# nao guarda estado entre execucoes, e clicar no cabecalho do expander nao
# reroda o script. Quem abre e fecha e o botao, para o formulario nao
# recolher sozinho no meio da digitacao.
CHAVE_FORM_NOVO = "form_novo_modulo_aberto"

# CSS proprio da pagina, no mesmo padrao do CSS_PERGAMINHOS (cada pagina
# guarda o que e so dela; modules/estilo.py fica com a identidade comum).
CSS_GERENCIAR_MODULOS = """
<style>
/* Rotulo de secao do formulario. O prefixo .stMarkdown p e obrigatorio:
   o Streamlit escreve ".stMarkdown p { font-size: ... }" (0,1,1), que
   ganha de um ".ce-secao" sozinho (0,1,0) -- a mesma armadilha explicada
   em modules/estilo.py. */
.stMarkdown p.ce-secao {
    color: #7dd3fc;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    margin: 0.2rem 0 0.9rem 0;
    padding-bottom: 0.35rem;
    border-bottom: 1px solid rgba(56, 189, 248, 0.28);
}
/* A previa usa o card verdadeiro (.ce-card) para o professor ver
   exatamente o que vai aparecer no mapa. O card real tem min-height de
   380px, pensado para a fileira de cards; na previa isso viraria um
   bloco enorme e vazio. */
.ce-previa .ce-card {
    min-height: auto;
}
.ce-previa {
    border: 1px dashed rgba(148, 163, 184, 0.28);
    border-radius: 14px;
    padding: 0.9rem;
    background: rgba(15, 23, 42, 0.35);
}
.stMarkdown p.ce-previa-titulo {
    color: #94a3b8;
    font-size: 0.78rem;
    margin: 0 0 0.6rem 0;
}
@media (max-width: 640px) {
    .stMarkdown p.ce-secao {
        font-size: 0.68rem;
    }
    .ce-previa {
        padding: 0.65rem;
    }
}
</style>
"""


def _html(trecho):
    """Atalho para html_bruto (ver a explicacao em modules/estilo.py)."""
    return html_bruto(trecho)


def _secao(titulo):
    """Desenha um rotulo de secao do formulario.

    O titulo e sempre literal do codigo (nunca digitado pelo usuario),
    por isso nao precisa de html.escape.
    """
    st.markdown(
        _html('<p class="ce-secao">%s</p>' % titulo),
        unsafe_allow_html=True,
    )


def _tipo():
    return st.session_state.get("tipo_usuario", "")


def _username():
    return st.session_state.get("username", "")


def _pode_gerenciar(modulo):
    """Admin gerencia tudo; os demais so os modulos que criaram no banco.

    Modulos especiais (o laboratorio AES) sao definidos no codigo e nao
    podem ser editados nem excluidos por esta tela, nem pelo Administrador.
    """
    if modulo.get("especial"):
        return False
    if _tipo() == "Administrador":
        return True
    return (
        modulo.get("origem") == "banco"
        and bool(modulo.get("autor"))
        and modulo.get("autor") == _username()
    )


def _k(prefixo, nome):
    return "%s_%s" % (prefixo, nome)


def _limpar_prefixo(prefixo):
    """Remove as chaves de um formulario, antes de qualquer widget da tela."""
    for chave in [c for c in list(st.session_state) if isinstance(c, str)]:
        if chave.startswith(prefixo + "_"):
            st.session_state.pop(chave, None)


def _limpar_edicoes():
    for prefixo in ("edit_modulo_", "edit_json_"):
        for chave in [c for c in list(st.session_state) if isinstance(c, str)]:
            if chave.startswith(prefixo):
                st.session_state.pop(chave, None)


def _iniciar(prefixo, modulo=None):
    """Preenche o formulario uma vez, quando ele abre.

    O "iniciado" e o que impede o formulario de ser sobrescrito a cada
    rerun: depois da primeira vez, quem manda sao os widgets e o que o
    usuario digitou.
    """
    if _k(prefixo, "iniciado") in st.session_state:
        return

    modulo = modulo or {}
    st.session_state[_k(prefixo, "iniciado")] = True
    st.session_state[_k(prefixo, "titulo")] = modulo.get("titulo", "")
    st.session_state[_k(prefixo, "slug")] = modulo.get("slug", "")
    st.session_state[_k(prefixo, "resumo")] = modulo.get("resumo", "")
    st.session_state[_k(prefixo, "icone")] = modulo.get("icone", "📘")
    st.session_state[_k(prefixo, "nivel")] = modulo.get("nivel", "")
    st.session_state[_k(prefixo, "dificuldade")] = modulo.get("dificuldade", "")
    st.session_state[_k(prefixo, "duracao")] = modulo.get("duracao", "")
    st.session_state[_k(prefixo, "cor")] = modulo.get("cor", "#4F46E5")

    quiz = modulo.get("quiz") or []
    st.session_state[_k(prefixo, "quiz_n")] = len(quiz)
    for indice, questao in enumerate(quiz):
        st.session_state[_k(prefixo, "q_enunciado_%d" % indice)] = (
            questao.get("enunciado", "")
        )
        st.session_state[_k(prefixo, "q_alternativas_%d" % indice)] = "\n".join(
            questao.get("alternativas", [])
        )
        certa = questao.get("certa", 0)
        if not isinstance(certa, int) or isinstance(certa, bool) or certa < 0:
            certa = 0
        st.session_state[_k(prefixo, "q_certa_%d" % indice)] = certa + 1


def _editor_quiz(prefixo):
    """Editor simples: uma caixa por pergunta, alternativas em linhas."""
    st.caption("Deixe 0 perguntas para criar um módulo sem quiz.")

    quantidade = int(st.number_input(
        "Quantidade de perguntas",
        min_value=0,
        max_value=MAX_PERGUNTAS,
        step=1,
        key=_k(prefixo, "quiz_n"),
    ))

    for indice in range(quantidade):
        with st.container(border=True):
            # O numero da pergunta usa o mesmo selo dos cards do mapa
            # (.ce-badge), em vez de um caption solto: fica claro onde
            # uma pergunta comeca e a outra termina.
            st.markdown(
                _html(
                    '<span class="ce-badge">Pergunta %d</span>'
                    % (indice + 1)
                ),
                unsafe_allow_html=True,
            )
            st.text_input(
                "Enunciado",
                key=_k(prefixo, "q_enunciado_%d" % indice),
            )
            texto = st.text_area(
                "Alternativas (uma por linha)",
                key=_k(prefixo, "q_alternativas_%d" % indice),
                height=100,
            )
            alternativas = [
                linha.strip() for linha in texto.splitlines() if linha.strip()
            ]
            chave_certa = _k(prefixo, "q_certa_%d" % indice)
            if len(alternativas) < 2:
                st.caption(
                    "Digite pelo menos duas alternativas para escolher a correta."
                )
                if chave_certa in st.session_state:
                    st.session_state[chave_certa] = 1
            else:
                atual = st.session_state.get(chave_certa, 1)
                if atual not in range(1, len(alternativas) + 1):
                    st.session_state[chave_certa] = 1
                st.selectbox(
                    "Alternativa correta",
                    options=list(range(1, len(alternativas) + 1)),
                    format_func=lambda numero: "Alternativa %d" % numero,
                    key=chave_certa,
                )


def _ler_quiz(prefixo):
    """Le o quiz digitado e devolve (lista, problemas)."""
    quantidade = int(st.session_state.get(_k(prefixo, "quiz_n"), 0) or 0)
    quiz = []
    problemas = []

    for indice in range(quantidade):
        enunciado = str(
            st.session_state.get(_k(prefixo, "q_enunciado_%d" % indice), "")
        ).strip()
        texto = str(
            st.session_state.get(_k(prefixo, "q_alternativas_%d" % indice), "")
        )
        alternativas = [
            linha.strip() for linha in texto.splitlines() if linha.strip()
        ]

        if not enunciado and not alternativas:
            continue
        if not enunciado or len(alternativas) < 2:
            problemas.append(
                "Pergunta %d: preencha o enunciado e pelo menos duas "
                "alternativas." % (indice + 1)
            )
            continue

        certa = int(
            st.session_state.get(_k(prefixo, "q_certa_%d" % indice), 1) or 1
        ) - 1
        if certa < 0 or certa >= len(alternativas):
            certa = 0

        quiz.append({
            "enunciado": enunciado,
            "alternativas": alternativas,
            "certa": certa,
        })

    return quiz, problemas


def _coletar(prefixo):
    """Le os campos do formulario e devolve (dados, problemas)."""
    titulo = str(st.session_state.get(_k(prefixo, "titulo"), "")).strip()
    slug = str(st.session_state.get(_k(prefixo, "slug"), "")).strip().lower()
    if not slug:
        slug = gerar_slug(titulo)

    quiz, problemas = _ler_quiz(prefixo)

    dados = {
        "titulo": titulo,
        "slug": slug,
        "resumo": str(st.session_state.get(_k(prefixo, "resumo"), "")).strip(),
        "icone": (
            str(st.session_state.get(_k(prefixo, "icone"), "")).strip() or "📘"
        ),
        "nivel": str(st.session_state.get(_k(prefixo, "nivel"), "")).strip(),
        "dificuldade": str(
            st.session_state.get(_k(prefixo, "dificuldade"), "")
        ).strip(),
        "duracao": str(st.session_state.get(_k(prefixo, "duracao"), "")).strip(),
        "cor": (
            str(st.session_state.get(_k(prefixo, "cor"), "")).strip()
            or "#4F46E5"
        ),
        "quiz": quiz,
    }
    return dados, problemas


def _slug_em_uso(slug, original=None):
    """Diz se o slug ja pertence a outro modulo (JSON ou banco)."""
    modulos, _ = carregar_modulos()
    for modulo in modulos:
        if modulo.get("slug") != slug:
            continue
        if original is not None and modulo.get("origem") == original.get("origem"):
            if (
                original.get("origem") == "banco"
                and modulo.get("id") == original.get("id")
            ):
                continue
            if (
                original.get("origem") == "json"
                and modulo.get("slug") == original.get("slug")
            ):
                continue
        return True
    return False


def _validar(dados, problemas, original=None):
    if not dados["titulo"]:
        return "Dê um título ao módulo."
    if not dados["slug"] or not RE_SLUG.match(dados["slug"]):
        return (
            "O slug só pode ter letra minúscula, número e hífen "
            "(ex.: senhas-e-autenticacao)."
        )
    if problemas:
        return " ".join(problemas)
    if _slug_em_uso(dados["slug"], original):
        return (
            "Já existe um módulo com o slug '%s'. Escolha outro."
            % dados["slug"]
        )
    return None


def _salvar_pdf(upload, slug, pdf_atual):
    """Grava o PDF enviado em static/modulos/<slug>.pdf.

    Devolve (nome_do_arquivo, erro). Sem upload, devolve o PDF atual,
    preservando o que ja estava la.
    """
    if upload is None:
        return pdf_atual, None

    tamanho = len(upload.getbuffer())
    if tamanho > MAX_PDF_MB * 1024 * 1024:
        return pdf_atual, (
            "O PDF passa do limite de %d MB. Envie um arquivo menor."
            % MAX_PDF_MB
        )

    nome = "%s.pdf" % slug
    caminho = os.path.join(PASTA_PDFS, nome)
    try:
        os.makedirs(PASTA_PDFS, exist_ok=True)
        with open(caminho, "wb") as arquivo:
            arquivo.write(upload.getbuffer())
    except OSError as erro:
        return pdf_atual, "Não consegui salvar o PDF: %s" % erro
    return nome, None


def _atualizar_banco(modulo_id, dados, pdf):
    """Atualiza um modulo do banco com os campos ja validados."""
    return atualizar_modulo(
        modulo_id,
        dados["slug"],
        dados["titulo"],
        dados["resumo"],
        dados["icone"],
        dados["nivel"],
        dados["dificuldade"],
        dados["duracao"],
        dados["cor"],
        pdf or "",
        dados["quiz"],
        _username(),
        _tipo(),
    )


def _previa_card(prefixo):
    """Mostra o card do mapa com os valores que estao no formulario.

    O desenho vem do proprio modules/mainmenu.py (_card_html), e nao de
    uma copia: assim a previa nunca diverge do card que o aluno ve. O
    _card_html ja passa tudo por html.escape.
    """
    def valor(nome, padrao):
        return (
            str(st.session_state.get(_k(prefixo, nome), "")).strip() or padrao
        )

    modulo = {
        "titulo": valor("titulo", "Título do módulo"),
        "resumo": valor("resumo", "Resumo do módulo."),
        "icone": valor("icone", "📘"),
        "nivel": valor("nivel", "Nível"),
        "dificuldade": valor("dificuldade", "Dificuldade"),
        "duracao": valor("duracao", "Duração"),
        "cor": valor("cor", "#4F46E5"),
    }

    st.markdown(
        _html(
            '<div class="ce-previa">'
            '<p class="ce-previa-titulo">Prévia do card no mapa</p>'
            + _card_html(modulo, False)
            + '</div>'
        ),
        unsafe_allow_html=True,
    )


def _campos_modulo(prefixo, modulo=None):
    """Desenha os campos comuns a criacao e a edicao. Devolve o upload.

    Os campos ficam agrupados em quatro secoes. A previa do card le os
    widgets ja desenhados (st.session_state), por isso ela vem depois
    deles: assim mostra o titulo/cor/icone que estao na tela naquele
    momento, sem precisar de um botao de "atualizar".
    """
    _secao("Identificação")
    st.text_input("Título", key=_k(prefixo, "titulo"))
    st.text_input(
        "Slug (identificador)",
        key=_k(prefixo, "slug"),
        help=(
            "É o nome curto do módulo, usado na URL e no nome do PDF. "
            "Deixe em branco para gerar a partir do título."
        ),
    )
    slug_digitado = str(
        st.session_state.get(_k(prefixo, "slug"), "")
    ).strip()
    if not slug_digitado:
        titulo_digitado = str(
            st.session_state.get(_k(prefixo, "titulo"), "")
        ).strip()
        slug_gerado = gerar_slug(titulo_digitado)
        if slug_gerado:
            st.caption("Sem slug: vai virar `%s`." % slug_gerado)
    st.text_area("Resumo", key=_k(prefixo, "resumo"), height=90)

    _secao("Aparência no mapa")
    coluna_campos, coluna_previa = st.columns([3, 2], gap="large")
    with coluna_campos:
        coluna_icone, coluna_cor = st.columns(2)
        coluna_icone.text_input("Ícone (um emoji)", key=_k(prefixo, "icone"))
        coluna_cor.color_picker("Cor do card", key=_k(prefixo, "cor"))

        coluna_nivel, coluna_dificuldade, coluna_duracao = st.columns(3)
        coluna_nivel.text_input("Nível", key=_k(prefixo, "nivel"))
        coluna_dificuldade.text_input(
            "Dificuldade", key=_k(prefixo, "dificuldade")
        )
        coluna_duracao.text_input("Duração", key=_k(prefixo, "duracao"))
    with coluna_previa:
        _previa_card(prefixo)

    _secao("Material")
    pdf_atual = (modulo or {}).get("pdf", "")
    if pdf_atual:
        st.caption("PDF atual: `%s`" % pdf_atual)

    upload = st.file_uploader(
        "Material em PDF",
        type=["pdf"],
        key=_k(prefixo, "pdf"),
        max_upload_size=MAX_PDF_MB,
        help=(
            "O arquivo é gravado em static/modulos/ com o nome do slug, "
            "até %d MB. Sem upload, o PDF atual é mantido." % MAX_PDF_MB
        ),
    )

    _secao("Quiz")
    _editor_quiz(prefixo)
    return upload


def _abrir_form_novo():
    st.session_state[CHAVE_FORM_NOVO] = True


def _recolher_form_novo():
    st.session_state[CHAVE_FORM_NOVO] = False


def _criar_modulo():
    """Cria o modulo a partir dos widgets, como callback do botao."""
    prefixo = "novo_modulo"
    dados, problemas = _coletar(prefixo)
    erro = _validar(dados, problemas)
    if erro:
        st.session_state["_aviso_modulos"] = ("error", erro)
        return

    upload = st.session_state.get(_k(prefixo, "pdf"))

    # A linha e criada primeiro, sem PDF. O arquivo so e gravado depois
    # que o slug passou pelo banco: se a criacao falhar, um PDF enviado
    # nao sobrescreve o material de outro modulo que por acaso use o
    # mesmo nome.
    novo_id, motivo = salvar_modulo(
        dados["slug"],
        dados["titulo"],
        dados["resumo"],
        dados["icone"],
        dados["nivel"],
        dados["dificuldade"],
        dados["duracao"],
        dados["cor"],
        "",
        dados["quiz"],
        _username(),
    )
    if novo_id is None:
        if motivo == "slug_duplicado":
            erro = "Já existe um módulo com esse slug. Escolha outro."
        else:
            erro = "Não consegui criar o módulo: %s" % motivo
        st.session_state["_aviso_modulos"] = ("error", erro)
        return

    # O catalogo e cacheado; a escrita no banco precisa derrubar a copia
    # antiga para o modulo novo aparecer no mapa imediatamente.
    carregar_modulos.clear()

    if upload is not None:
        pdf, erro_pdf = _salvar_pdf(upload, dados["slug"], "")
        if erro_pdf:
            st.session_state["_aviso_modulos"] = (
                "warning",
                "Módulo criado, mas o PDF não foi salvo: %s" % erro_pdf,
            )
        else:
            ok, motivo = _atualizar_banco(novo_id, dados, pdf)
            if not ok:
                try:
                    os.remove(os.path.join(PASTA_PDFS, pdf))
                except OSError:
                    pass
                st.session_state["_aviso_modulos"] = (
                    "warning",
                    "Módulo criado, mas não consegui anexar o PDF: %s"
                    % motivo,
                )

    st.session_state["_limpar_novo_modulo"] = True
    st.session_state[CHAVE_FORM_NOVO] = False
    if "_aviso_modulos" not in st.session_state:
        st.session_state["_aviso_modulos"] = (
            "success",
            "Módulo criado!",
        )


def _salvar_edicao(modulo):
    """Valida e grava a edicao, como callback do botao."""
    prefixo = _prefixo_edicao(modulo)
    dados, problemas = _coletar(prefixo)
    erro = _validar(dados, problemas, original=modulo)
    if erro:
        st.session_state["_aviso_modulos"] = ("error", erro)
        return

    upload = st.session_state.get(_k(prefixo, "pdf"))
    pdf, erro_pdf = _salvar_pdf(
        upload, dados["slug"], modulo.get("pdf", "")
    )
    if erro_pdf:
        st.session_state["_aviso_modulos"] = ("error", erro_pdf)
        return

    if modulo.get("origem") == "banco":
        ok, motivo = _atualizar_banco(modulo["id"], dados, pdf)
        if not ok:
            if motivo == "sem_permissao":
                erro = "Você só pode editar os módulos que criou."
            elif motivo == "slug_duplicado":
                erro = "Já existe um módulo com esse slug."
            else:
                erro = "Não consegui salvar: %s" % motivo
            st.session_state["_aviso_modulos"] = ("error", erro)
            return
    else:
        ok, motivo = atualizar_modulo_json(modulo["slug"], {
            "slug": dados["slug"],
            "titulo": dados["titulo"],
            "resumo": dados["resumo"],
            "icone": dados["icone"],
            "nivel": dados["nivel"],
            "dificuldade": dados["dificuldade"],
            "duracao": dados["duracao"],
            "cor": dados["cor"],
            "pdf": pdf or "",
            "quiz": _quiz_para_json(dados["quiz"]),
        })
        if not ok:
            st.session_state["_aviso_modulos"] = (
                "error",
                "Não consegui salvar o módulo: %s" % motivo,
            )
            return

    carregar_modulos.clear()
    st.session_state["_limpar_edicao_modulo"] = True
    st.session_state.pop("modulo_em_edicao", None)
    st.session_state["_aviso_modulos"] = (
        "success",
        "Módulo atualizado.",
    )


def _cancelar_edicao():
    st.session_state["_limpar_edicao_modulo"] = True
    st.session_state.pop("modulo_em_edicao", None)


def _abrir_edicao(referencia):
    st.session_state["_limpar_edicao_modulo"] = True
    st.session_state["modulo_em_edicao"] = referencia
    st.session_state.pop("modulo_excluindo", None)


def _pedir_exclusao(referencia):
    st.session_state.pop("modulo_em_edicao", None)
    st.session_state["modulo_excluindo"] = referencia


def _executar_exclusao(modulo):
    if modulo.get("origem") == "banco":
        ok, motivo = excluir_modulo(modulo["id"], _username(), _tipo())
        if not ok:
            if motivo == "sem_permissao":
                erro = "Você só pode excluir os módulos que criou."
            else:
                erro = "Não consegui excluir: %s" % motivo
            st.session_state["_aviso_modulos"] = ("error", erro)
            return
    else:
        ok, motivo = excluir_modulo_json(modulo["slug"])
        if not ok:
            st.session_state["_aviso_modulos"] = (
                "error",
                "Não consegui excluir: %s" % motivo,
            )
            return

    carregar_modulos.clear()
    st.session_state["_limpar_edicao_modulo"] = True
    st.session_state.pop("modulo_excluindo", None)
    st.session_state["_aviso_modulos"] = ("success", "Módulo excluído.")


def _cancelar_exclusao():
    st.session_state.pop("modulo_excluindo", None)


def _formulario_novo():
    prefixo = "novo_modulo"

    # Recolhido por padrao: a pagina abre com a lista de modulos visivel,
    # e nao com um formulario longo empurrando tudo para baixo. Quem
    # controla o estado e o botao, e nao o cabecalho do st.expander --
    # clicar no cabecalho nao reroda o script, entao o expander voltaria
    # a fechar no primeiro rerun de qualquer tecla.
    if not st.session_state.get(CHAVE_FORM_NOVO, False):
        st.button(
            "Criar novo módulo",
            type="primary",
            key="abrir_form_novo",
            icon=":material/add:",
            on_click=_abrir_form_novo,
        )
        return

    _iniciar(prefixo)

    with st.expander("➕ Criar novo módulo", expanded=True):
        st.caption(
            "O módulo novo é gravado no banco e já aparece no mapa de missões."
        )
        _campos_modulo(prefixo)

        coluna_criar, coluna_recolher = st.columns([2, 1])
        coluna_criar.button(
            "Criar módulo",
            type="primary",
            key="criar_modulo_novo",
            icon=":material/add:",
            on_click=_criar_modulo,
        )
        coluna_recolher.button(
            "Recolher",
            key="recolher_form_novo",
            icon=":material/close:",
            on_click=_recolher_form_novo,
        )


def _prefixo_edicao(modulo):
    if modulo.get("origem") == "banco":
        return "edit_modulo_%s" % modulo.get("id")
    return "edit_json_%s" % modulo.get("slug", "")


def _quiz_para_json(quiz):
    """Converte o quiz interno (0-based) para o formato do JSON (1-based)."""
    return [
        {
            "enunciado": questao["enunciado"],
            "alternativas": questao["alternativas"],
            "certa": int(questao["certa"]) + 1,
        }
        for questao in quiz
    ]


def _formulario_editar(modulo):
    if modulo.get("especial"):
        st.error(
            "Este módulo é especial e só pode ser editado no código "
            "(dados/modulos.json e o PDF em static/modulos/)."
        )
        return

    prefixo = _prefixo_edicao(modulo)
    _iniciar(prefixo, modulo)

    st.markdown("#### Editando: %s" % modulo.get("titulo", ""))
    if modulo.get("origem") == "json":
        st.caption(
            "Este módulo é um dos originais e será alterado em "
            "dados/modulos.json."
        )
    else:
        st.caption(
            "Este módulo foi criado na plataforma por %s."
            % (modulo.get("autor") or "—")
        )

    _campos_modulo(prefixo, modulo)

    coluna_salvar, coluna_cancelar = st.columns(2)
    coluna_salvar.button(
        "Salvar alterações",
        type="primary",
        key="salvar_%s" % prefixo,
        icon=":material/save:",
        on_click=_salvar_edicao,
        args=(modulo,),
    )
    coluna_cancelar.button(
        "Cancelar edição",
        key="cancelar_%s" % prefixo,
        icon=":material/close:",
        on_click=_cancelar_edicao,
    )


def _confirmar_exclusao(modulo):
    if modulo.get("especial"):
        st.error(
            "Este módulo é especial e só pode ser excluído no código "
            "(dados/modulos.json)."
        )
        return

    st.warning(
        "Excluir o módulo **%s**? Essa ação não pode ser desfeita."
        % modulo.get("titulo", "")
    )
    if modulo.get("origem") == "banco":
        st.caption(
            "O histórico de leituras e notas dos alunos continua no banco."
        )
    else:
        st.caption(
            "O módulo será retirado de dados/modulos.json. O arquivo PDF "
            "não é apagado."
        )

    chave = modulo.get("id") if modulo.get("origem") == "banco" else modulo.get("slug")
    coluna_sim, coluna_nao = st.columns(2)
    coluna_sim.button(
        "Sim, excluir",
        type="primary",
        key="confirmar_exclusao_%s" % chave,
        icon=":material/delete:",
        on_click=_executar_exclusao,
        args=(modulo,),
    )
    coluna_nao.button(
        "Cancelar",
        key="cancelar_exclusao_%s" % chave,
        icon=":material/close:",
        on_click=_cancelar_exclusao,
    )


def _achar_modulo(modulos, referencia):
    """Encontra o modulo apontado por (origem, id_ou_slug)."""
    if not referencia:
        return None
    try:
        origem, chave = referencia
    except (TypeError, ValueError):
        return None

    for modulo in modulos:
        if modulo.get("origem") != origem:
            continue
        if origem == "banco" and modulo.get("id") == chave:
            return modulo
        if origem == "json" and modulo.get("slug") == chave:
            return modulo
    return None


def render_gerenciar_modulos():
    """Pagina de gerenciamento dos modulos, para Professor e Administrador."""
    with st.container(key="pagina_gerenciar_modulos"):
        _render_gerenciar_modulos()


def _render_gerenciar_modulos():
    aplicar_estilo()

    # A pagina so e alcancavel pelo menu de Professor/Administrador, mas
    # a checagem fica aqui tambem: a regra de acesso nao deve depender de
    # o item do menu ter sido escondido.
    if _tipo() not in ("Professor", "Administrador"):
        st.error("Acesso restrito a professores e administradores.")
        return

    st.markdown(CSS_GERENCIAR_MODULOS, unsafe_allow_html=True)

    # As limpezas vem antes de qualquer widget: mexer em chave de widget
    # depois que ele nasceu, na mesma execucao, levanta erro no Streamlit.
    if st.session_state.pop("_limpar_novo_modulo", False):
        _limpar_prefixo("novo_modulo")
    if st.session_state.pop("_limpar_edicao_modulo", False):
        _limpar_edicoes()

    aviso = st.session_state.pop("_aviso_modulos", None)
    if aviso:
        getattr(st, aviso[0])(aviso[1])

    st.markdown(
        _html(
            """
            <p class="ce-pixel">GERENCIAR MÓDULOS</p>
            <p class="ce-subtitulo">Crie módulos novos ou edite os que já existem. Quem criou um módulo pode editá-lo e excluí-lo; o Administrador pode gerenciar todos. O laboratório AES é um módulo especial e só pode ser alterado no código.</p>
            """
        ),
        unsafe_allow_html=True,
    )

    _formulario_novo()

    modulos, erros = carregar_modulos()
    if erros:
        with st.expander("⚠️ Problemas ao carregar os módulos", expanded=False):
            for erro in erros:
                st.error(erro)

    st.divider()
    st.subheader("Módulos cadastrados")

    if not modulos:
        st.info("Nenhum módulo cadastrado.")
        return

    alvo_edicao = _achar_modulo(
        modulos, st.session_state.get("modulo_em_edicao")
    )
    if alvo_edicao is not None and _pode_gerenciar(alvo_edicao):
        _formulario_editar(alvo_edicao)
        st.divider()

    alvo_exclusao = _achar_modulo(
        modulos, st.session_state.get("modulo_excluindo")
    )
    if alvo_exclusao is not None and _pode_gerenciar(alvo_exclusao):
        _confirmar_exclusao(alvo_exclusao)
        st.divider()

    for modulo in modulos:
        origem = modulo.get("origem")
        rotulo_origem = (
            "pré-existente (JSON)"
            if origem == "json"
            else "criado na plataforma"
        )
        autor = modulo.get("autor") or "—"

        with st.expander(
            "%s  %s" % (modulo.get("icone", "📘"), modulo.get("titulo", "")),
            expanded=False,
        ):
            st.caption(
                "Origem: %s · Autor: %s" % (rotulo_origem, autor)
            )
            if modulo.get("resumo"):
                st.write(modulo["resumo"])
            st.caption(
                "%d pergunta(s) de quiz · %s"
                % (
                    len(modulo.get("quiz") or []),
                    modulo.get("pdf") or "sem PDF",
                )
            )

            if modulo.get("especial"):
                st.caption(
                    "🧪 Módulo especial definido no código. Para alterar o "
                    "material ou o quiz, edite `dados/modulos.json` e o PDF "
                    "em `static/modulos/`."
                )
                continue

            if not _pode_gerenciar(modulo):
                st.caption(
                    "Somente quem criou este módulo (ou um Administrador) "
                    "pode editá-lo ou excluí-lo."
                )
                continue

            chave = (
                modulo.get("id")
                if origem == "banco"
                else modulo.get("slug")
            )
            referencia = (origem, chave)
            coluna_editar, coluna_excluir = st.columns(2)

            coluna_editar.button(
                "Editar",
                key="editar_%s_%s" % (origem, chave),
                icon=":material/edit:",
                on_click=_abrir_edicao,
                args=(referencia,),
            )

            coluna_excluir.button(
                "Excluir",
                key="excluir_%s_%s" % (origem, chave),
                icon=":material/delete:",
                on_click=_pedir_exclusao,
                args=(referencia,),
            )
