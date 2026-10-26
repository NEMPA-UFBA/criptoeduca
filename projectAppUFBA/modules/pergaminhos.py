"""A pagina dos pergaminhos: os exemplos de crimes digitais.

Cada exemplo de golpe e um PERGAMINHO: uma roleta de papel que a pessoa
clica para abrir, e que mostra a mensagem falsa do golpe, os sinais de
alerta e o que fazer. Clicar em outro pergaminho fecha o anterior -- e
por isso que o estado do pergaminho aberto mora em st.session_state, e
nao em um st.expander: o expander do Streamlit deixa dois abertos ao
mesmo tempo, e o que se quer aqui e um so.

De onde vem o conteudo:

  - dos exemplos pre-colocados em dados/exemplos_crime.json, semeados no
    primeiro boot (o texto e um molde, em lorem ipsum, para o professor
    trocar pelo conteudo real);
  - do que o Professor e a Coordenacao publicam em "Gerenciar Aulas".

Os dois sao a mesma coisa na tela: um pergaminho. Por isso o que a
coordenacao publica vira parte dos pergaminhos, e nao uma pagina
separada.
"""

import html

import streamlit as st

from modules.database import (
    carregar_pergaminhos,
    salvar_conteudo,
    atualizar_conteudo,
    inativar_conteudo,
)
from modules.estilo import html_bruto
from modules.exemplos_crime import texto_para_linhas

# Chave da sessao que guarda o id do pergaminho aberto. Um so pergaminho
# aberto por vez: e a sessao que garante isso, nao o CSS.
CHAVE_ABERTO = "pergaminho_aberto"

# Categorias oferecidas no formulario de publicacao. A primeira e a que
# aparece no comeco; "Outro" deixa o professor digitar a dele.
CATEGORIAS = [
    "Financeiro",
    "Engenharia Social",
    "Roubo de Identidade",
    "Outro",
]

# Os mesmos tons do resto do app, mas do lado de dentro do papel: o
# pergaminho e claro, e o texto sobre ele e escuro. Sem isso o texto
# claro do app sumiria em cima do papel.
CSS_PERGAMINHOS = """
<style>
/* ==========================================================================
   O PERGAMINHO
   ==========================================================================
   A ideia e fazer o papel parecer papel: um rolo de madeira com o pergaminho
   enrolado em cima, e a folha aberta embaixo, amarelada, com manchas, com a
   borda rasgada e com a tinta escura por cima.

   As tres peças sao:

     1. A ROLTA (o botao do Streamlit) -- a ponta enrolada do pergaminho,
        apoiada nas duas varas de madeira. E o que a pessoa clica.
     2. A FOLHA (o miolo) -- o papel aberto, com as manchas e a borda rasgada.
     3. O TEXTO -- a tinta, em cor de tinta ferrogálica sobre papel.

   Os seletores sao por ATRIBUTO e nao por classe. A classe que o Streamlit
   monta e "st-key-" + o key inteiro, ou seja "st-key-pergaminho_3" e
   "st-key-pergaminho_aberto_3". Um seletor de classe exato nao casaria com
   nenhuma das duas. O seletor por atributo casa com as duas -- "st-key-
   pergaminho_" esta dentro de "st-key-pergaminho_aberto_3" -- e por isso a
   regra do aberto vem depois, para sobrescrever.
   ========================================================================== */

/* ---------- 1. A ROLTA: o botao que abre ---------- */
[class*="st-key-pergaminho_"] button {
    position: relative;
    width: 100%;
    text-align: left;
    padding: 0.55rem 3.2rem 0.55rem 1.1rem;
    color: #f3e6c8;
    font-weight: 700;
    font-size: 0.98rem;
    letter-spacing: 0.01em;
    /* O gradiente de cima para baixo e o que faz o papel enrolado parecer
       um cilindro: a parte de cima recebe a luz, a de baixo fica na
       sombra. Uma cor só nao daria a.volume nenhum. */
    background:
        linear-gradient(180deg,
            #d9c18c 0%,
            #c9ad74 12%,
            #b8995f 30%,
            #ab8a52 50%,
            #b8995f 70%,
            #c9ad74 88%,
            #8e7141 100%);
    border: 1px solid #6b5228;
    /* O canto de cima e de baixo arredondados e o que faz parecer que o
       papel esta enrolado; as pontas de madeira entram por cima, com os
       pseudo-elementos abaixo. */
    border-radius: 14px 14px 5px 5px;
    box-shadow:
        inset 0 1px 0 rgba(255, 240, 200, 0.45),
        inset 0 -3px 6px rgba(60, 40, 10, 0.5),
        0 4px 12px rgba(0, 0, 0, 0.45);
    transition: transform 0.18s ease, filter 0.18s ease,
                box-shadow 0.18s ease;
}
/* As duas varas de madeira atravessando o rolo. Sao os pseudo-elementos:
   ::before fica na ponta esquerda e ::after na direita, e cada um e uma
   vara com o gradiente transversal que imita o veio da madeira. */
[class*="st-key-pergaminho_"] button::before,
[class*="st-key-pergaminho_"] button::after {
    content: "";
    position: absolute;
    top: -3px;
    bottom: -3px;
    width: 16px;
    background:
        linear-gradient(90deg,
            #4a3316 0%,
            #8a6428 22%,
            #b8893f 42%,
            #7d5a22 68%,
            #513916 100%);
    border: 1px solid #33240d;
    border-radius: 4px;
    box-shadow:
        inset 0 1px 0 rgba(255, 225, 170, 0.35),
        0 2px 4px rgba(0, 0, 0, 0.5);
}
[class*="st-key-pergaminho_"] button::before {
    left: -2px;
}
[class*="st-key-pergaminho_"] button::after {
    right: -2px;
}
[class*="st-key-pergaminho_"] button:hover {
    filter: brightness(1.09) saturate(1.05);
    transform: translateY(-1px);
    box-shadow:
        inset 0 1px 0 rgba(255, 240, 200, 0.55),
        inset 0 -3px 6px rgba(60, 40, 10, 0.5),
        0 7px 18px rgba(0, 0, 0, 0.5);
}
[class*="st-key-pergaminho_"] button:active {
    transform: translateY(1px);
}
/* O texto do botao e o titulo do golpe. A sombra em cima e a mesma ilusao
   de relevo que o Streamlit aplica nos botoes claros, so que invertida
   para o texto claro sobre o rolo escuro. */
[class*="st-key-pergaminho_"] button p {
    color: #f3e6c8;
    font-weight: 700;
    text-shadow: 0 1px 1px rgba(40, 25, 5, 0.75);
}
/* O pergaminho aberto: a ponta foi puxada, e o rolo fica com a madeira a
   mostra, mais claro e mais alto. */
[class*="st-key-pergaminho_aberto_"] button {
    background:
        linear-gradient(180deg,
            #ecd9a8 0%,
            #dcc18a 14%,
            #cbae72 34%,
            #bf9f60 52%,
            #cbae72 70%,
            #ddc18c 88%,
            #a3854c 100%);
    color: #3d2c11;
    border-color: #5d461f;
    border-radius: 16px 16px 4px 4px;
    box-shadow:
        inset 0 1px 0 rgba(255, 245, 215, 0.6),
        inset 0 -4px 8px rgba(60, 40, 10, 0.45),
        0 9px 22px rgba(0, 0, 0, 0.5);
}
[class*="st-key-pergaminho_aberto_"] button p {
    color: #3d2c11;
    text-shadow: 0 1px 0 rgba(255, 240, 205, 0.5);
}
/* O rotulo do botao leva um emoji, que o Streamlit bota junto do texto. O
   espacamento a direita foi aumentado para o texto nao passar por baixo da
   vara de madeira da ponta. */

/* ---------- 2. A FOLHA: o papel aberto ---------- */
/* A sombra do papel fica no ENVOLTORIO, e nao na folha.
   A folha usa clip-path para serrar a borda em dentes -- e o clip-path
   recorta a sombra junto. A sombra entao vai no wrapper, com
   filter: drop-shadow, que enxerga a silhueta ja recortada e projeta a
   sombra no contorno dos dentes, e nao num retangulo. */
.ce-pergaminho-sombra {
    margin: -1rem 0 1.4rem 0;
    filter: drop-shadow(0 10px 20px rgba(0, 0, 0, 0.45))
            drop-shadow(0 2px 4px rgba(0, 0, 0, 0.3));
}
.ce-pergaminho {
    position: relative;
    color: #3d2c14;
    /* A serifada vem no container, e nao so nos filhos: e o que garante
       que qualquer texto que caia aqui dentro (inclusive o que o
       Streamlit escrever) saia com cara de documento antigo. */
    font-family: Georgia, "Times New Roman", serif;
    padding: 1.35rem 1.6rem 1.6rem 1.6rem;
    /* A borda rasgada e feita com tres coisas ao mesmo tempo:
         - o gradiente que mancha o papel em varios pontos;
         - o recorte (clip-path) que serra a borda em dentes irregulares;
         - a sombra interna, que escurece as beiradas.
       Uma folha de papel velho nao tem borda reta: e por isso que o
       clip-path tem aquelas medidas assim tresnadas. */
    background:
        radial-gradient(ellipse at 12% 8%, rgba(120, 85, 30, 0.16) 0%, rgba(120, 85, 30, 0) 42%),
        radial-gradient(ellipse at 88% 22%, rgba(140, 95, 35, 0.13) 0%, rgba(140, 95, 35, 0) 38%),
        radial-gradient(ellipse at 72% 88%, rgba(110, 75, 25, 0.15) 0%, rgba(110, 75, 25, 0) 40%),
        radial-gradient(ellipse at 26% 78%, rgba(150, 105, 40, 0.11) 0%, rgba(150, 105, 40, 0) 34%),
        radial-gradient(circle at 50% 50%, rgba(255, 250, 230, 0.5) 0%, rgba(255, 250, 230, 0) 70%),
        linear-gradient(168deg, #e9d6a6 0%, #e2cb95 45%, #d8bd82 100%);
    clip-path: polygon(
        0.4% 0%, 8% 0.7%, 17% 0%, 27% 0.9%, 38% 0.2%, 49% 1%, 61% 0.1%, 72% 0.8%,
        84% 0%, 93% 0.6%, 99.5% 0.1%, 100% 6%, 99.7% 18%, 100% 32%, 99.6% 48%,
        100% 63%, 99.8% 78%, 100% 92%, 99.4% 100%, 88% 99.3%, 76% 100%, 64% 99.2%,
        51% 100%, 39% 99.1%, 27% 100%, 16% 99.4%, 6% 100%, 0.3% 99.6%, 0% 90%,
        0.4% 76%, 0% 61%, 0.5% 46%, 0% 32%, 0.4% 18%, 0.1% 7%
    );
    box-shadow:
        inset 0 0 30px rgba(110, 75, 25, 0.22),
        inset 0 0 6px rgba(90, 60, 20, 0.18);
}
/* A costura do papel: a dobra onde o pergaminho foi dobrado para caber
   na roleta. E a sombra suave que desce do rolo de madeira. */
.ce-pergaminho::before {
    content: "";
    position: absolute;
    left: 0;
    right: 0;
    top: 0;
    height: 26px;
    background: linear-gradient(180deg, rgba(70, 45, 12, 0.42), rgba(70, 45, 12, 0));
    pointer-events: none;
}
/* A mancha de cera que fecha o pergaminho. Fica no canto, como o lacre de
   um documento antigo. */
.ce-pergaminho::after {
    content: "";
    position: absolute;
    right: 22px;
    top: 18px;
    width: 34px;
    height: 34px;
    border-radius: 50%;
    background:
        radial-gradient(circle at 34% 30%, #b8382c 0%, #8e2a20 45%, #6b1d15 100%);
    box-shadow:
        inset 0 -2px 4px rgba(0, 0, 0, 0.45),
        inset 0 2px 3px rgba(255, 180, 160, 0.35),
        0 2px 4px rgba(0, 0, 0, 0.4);
    opacity: 0.9;
    pointer-events: none;
}
/* A tinta. O titulo e mais escuro e mais fechado do que o corpo, como no
   documento antigo. O espaco a direita existe para o titulo nao passar por
   baixo do lacre de cera, que fica no canto. */
.ce-pergaminho h3 {
    margin: 0 0 0.15rem 0;
    padding-right: 3.2rem;
    font-size: 1.18rem;
    font-weight: 700;
    color: #33240e;
    letter-spacing: 0.01em;
    font-family: Georgia, "Times New Roman", serif;
}
/* O subtitulo da categoria, em caixa alta e espacado: e a "rubrica" do
   documento. */
.ce-pergaminho-categoria {
    display: inline-block;
    color: #7a5c28;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    margin-bottom: 0.5rem;
    font-family: Georgia, "Times New Roman", serif;
}
.ce-pergaminho p {
    margin: 0 0 0.95rem 0;
    line-height: 1.65;
    color: #4a3618;
    font-family: Georgia, "Times New Roman", serif;
    font-size: 0.97rem;
}
/* A mensagem falsa do golpe, como se tivesse sido escrita numa tira de
   papel e colada no documento. O papel e mais claro e a borda e serrada
   de outro jeito. */
.ce-pergaminho-exemplo {
    background:
        linear-gradient(175deg, #f6ecc9 0%, #eddfb4 100%);
    border: 1px dashed #9a7a3e;
    border-radius: 3px;
    padding: 0.85rem 1rem;
    margin: 0 0 1.1rem 0;
    box-shadow: inset 0 1px 4px rgba(120, 85, 30, 0.18);
    transform: rotate(-0.35deg);
}
.ce-pergaminho-exemplo p {
    margin: 0;
    font-family: "Courier New", monospace;
    font-size: 0.9rem;
    color: #3f2c11;
    line-height: 1.6;
}
/* O rotulo das secoes, em caixa alta, como o titulo de um capitulo. */
.ce-pergaminho-titulo-secao {
    font-weight: 700;
    color: #6b4f21;
    font-size: 0.76rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    margin: 0 0 0.4rem 0;
    font-family: Georgia, "Times New Roman", serif;
    /* A linha fina embaixo do rotulo e a mesma coisa nas secoes do
       documento antigo: um filete separando o titulo do texto. */
    border-bottom: 1px solid rgba(107, 79, 33, 0.35);
    padding-bottom: 0.25rem;
}
.ce-pergaminho ul {
    margin: 0 0 1.1rem 0;
    padding-left: 1.35rem;
}
.ce-pergaminho li {
    color: #4a3618;
    line-height: 1.6;
    margin-bottom: 0.3rem;
    font-family: Georgia, "Times New Roman", serif;
    font-size: 0.95rem;
}
/* O marcador da lista e um pontinho, do mesmo jeito que no documento
   antigo -- o Streamlit botaria um triangulo, que grita com o papel. */
.ce-pergaminho li::marker {
    color: #8a6a30;
}
/* O credito, no rodape do documento. */
.ce-pergaminho-credito {
    font-size: 0.76rem;
    color: #8a6b38;
    margin: 0;
    font-style: italic;
    font-family: Georgia, "Times New Roman", serif;
}
.ce-pergaminho-rodape {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
    align-items: center;
    margin-bottom: 0.8rem;
}
/* Em tela estreita (celular de aluno) o papel aperta: a borda rasgada
   continua, mas o texto ganha folga. */
@media (max-width: 640px) {
    .ce-pergaminho {
        padding: 1.1rem 1.15rem 1.3rem 1.15rem;
    }
    .ce-pergaminho-sombra {
        margin: -1rem 0 1.2rem 0;
    }
    [class*="st-key-pergaminho_"] button {
        padding: 0.55rem 2.9rem 0.55rem 0.9rem;
        font-size: 0.9rem;
    }
}
/* Quem pede menos animacao nao recebe transform nem transicao */
@media (prefers-reduced-motion: reduce) {
    [class*="st-key-pergaminho_"] button {
        transition: none;
    }
    [class*="st-key-pergaminho_"] button:hover {
        transform: none;
    }
    .ce-pergaminho-exemplo {
        transform: none;
    }
}
</style>
"""


def _html(trecho):
    """Atalho para html_bruto (ver a explicação lá)."""
    return html_bruto(trecho)


def _lista_em_html(itens):
    """Monta a <ul> de um bloco de linhas, ou nada se não houver linhas."""
    if not itens:
        return ""
    pecas = []
    for item in itens:
        pecas.append("<li>%s</li>" % html.escape(item))
    return "<ul>%s</ul>" % "".join(pecas)


def _miolo_html(pergaminho):
    """HTML do miolo aberto: a mensagem falsa, os sinais e a protecao."""
    categoria = html.escape(pergaminho.get("categoria") or "")
    titulo_categoria = ""
    if categoria:
        titulo_categoria = (
            '<span class="ce-pergaminho-categoria">%s</span>' % categoria
        )

    exemplo = (pergaminho.get("exemplo") or "").strip()
    bloco_exemplo = ""
    if exemplo:
        bloco_exemplo = (
            '<div class="ce-pergaminho-exemplo"><p>%s</p></div>'
            % html.escape(exemplo)
        )

    sinais = texto_para_linhas(pergaminho.get("sinais") or "")
    protecao = texto_para_linhas(pergaminho.get("protecao") or "")

    bloco_sinais = ""
    if sinais:
        bloco_sinais = (
            '<p class="ce-pergaminho-titulo-secao">Sinais de alerta</p>%s'
            % _lista_em_html(sinais)
        )

    bloco_protecao = ""
    if protecao:
        bloco_protecao = (
            '<p class="ce-pergaminho-titulo-secao">Como se proteger</p>%s'
            % _lista_em_html(protecao)
        )

    credito = ""
    autor = pergaminho.get("autor") or ""
    data = pergaminho.get("data") or ""
    if autor or data:
        pedacos = []
        if autor:
            pedacos.append("Publicado por %s" % html.escape(str(autor)))
        if data:
            pedacos.append(str(data))
        credito = '<p class="ce-pergaminho-credito">%s</p>' % " &middot; ".join(
            pedacos
        )

    corpo = html.escape(pergaminho.get("corpo") or "")
    titulo = html.escape(pergaminho.get("titulo") or "")

    return _html(
        f"""
        <div class="ce-pergaminho-sombra">
          <div class="ce-pergaminho">
            <div class="ce-pergaminho-rodape">{titulo_categoria}</div>
            <h3>{titulo}</h3>
            <p>{corpo}</p>
            {bloco_exemplo}
            {bloco_sinais}
            {bloco_protecao}
            {credito}
          </div>
        </div>
        """
    )


def render_pergaminhos():
    """Desenha a pagina de exemplos de crimes digitais (o pergaminhos)."""
    st.markdown(CSS_PERGAMINHOS, unsafe_allow_html=True)

    st.markdown(
        _html(
            """
            <p class="ce-pixel">EXEMPLOS DE CRIMES DIGITAIS</p>
            <p class="ce-subtitulo">Clique em um pergaminho para abrir o exemplo do golpe. Ao clicar em outro, o anterior fecha.</p>
            """
        ),
        unsafe_allow_html=True,
    )

    pergaminhos = carregar_pergaminhos()

    if not pergaminhos:
        st.info(
            "Nenhum exemplo de crime cadastrado ainda. Os exemplos "
            "pré-colocados vêm do arquivo `dados/exemplos_crime.json`, e o "
            "Professor e a Coordenação publicam os novos em "
            "\"Gerenciar Aulas\"."
        )
        return

    # O pergaminho aberto. Um so: clicar no mesmo fecha, clicar em outro
    # troca. A chave fica na sessao porque o Streamlit redesenha a tela
    # inteira a cada clique.
    aberto = st.session_state.get(CHAVE_ABERTO)

    for pergaminho in pergaminhos:
        pid = pergaminho["id"]
        icone = pergaminho.get("icone") or "📜"
        titulo = pergaminho.get("titulo") or ""
        esta_aberto = aberto == pid

        # O key muda conforme o estado: assim o CSS consegue distinguir o
        # pergaminho aberto do fechado, porque a classe st-key-* do
        # Streamlit vem do key do widget.
        if esta_aberto:
            chave_widget = f"pergaminho_aberto_{pid}"
        else:
            chave_widget = f"pergaminho_{pid}"

        if st.button(
            f"{icone}  {titulo}",
            key=chave_widget,
            width="stretch",
        ):
            if esta_aberto:
                # Clicar no que ja estava aberto fecha.
                st.session_state[CHAVE_ABERTO] = None
            else:
                st.session_state[CHAVE_ABERTO] = pid
            st.rerun()

        if esta_aberto:
            st.markdown(_miolo_html(pergaminho), unsafe_allow_html=True)


def _formulario_publicar():
    """Formulario de publicacao de um exemplo de crime.

    Fica dentro de um st.form para que o texto nao se mexa a cada tecla.
    """
    with st.form("form_publicar_crime", clear_on_submit=True):
        titulo = st.text_input("Título do golpe")
        icone = st.text_input("Ícone (um emoji)", value="📜")
        categoria = st.selectbox("Categoria", CATEGORIAS)
        categoria_livre = ""
        if categoria == "Outro":
            categoria_livre = st.text_input("Escreva a categoria")
        corpo = st.text_area("Descrição do golpe", height=140)
        exemplo = st.text_area(
            "Exemplo de mensagem (como a pessoa receberia)",
            height=120,
        )
        sinais = st.text_area(
            "Sinais de alerta (um por linha)",
            height=120,
        )
        protecao = st.text_area(
            "Como se proteger (um por linha)",
            height=120,
        )
        publicar = st.form_submit_button("Publicar exemplo")

    if publicar:
        if not titulo.strip() or not corpo.strip():
            st.error("Preencha pelo menos o título e a descrição.")
            return
        salvar_conteudo(
            titulo.strip(),
            corpo.strip(),
            st.session_state.get("username", ""),
            icone.strip() or "📜",
            (categoria_livre.strip() if categoria == "Outro" else categoria),
            exemplo.strip(),
            sinais.strip(),
            protecao.strip(),
        )
        st.success("Exemplo publicado! Ele já aparece como pergaminho.")
        st.rerun()


def _preencher_campos_edicao(pergaminho):
    """Escreve os valores do exemplo nos campos de edicao, uma vez so.

    Os campos do Streamlit nao aceitam mudar de valor depois de criados
    nesta execucao, entao o preenchimento acontece por session_state,
    antes do widget existir.

    O preenchimento acontece UMA VEZ por exemplo. Se fosse a cada
    execucao, qualquer outro clique na tela -- o de inativar outro
    exemplo, por exemplo -- reescreveria os campos e apagaria o que a
    pessoa estava escrevendo. O guarda _crime_prefill_id diz qual
    exemplo foi o ultimo a ser preenchido.
    """
    if st.session_state.get("_crime_prefill_id") == pergaminho["id"]:
        return

    st.session_state["ed_titulo"] = pergaminho.get("titulo") or ""
    st.session_state["ed_icone"] = pergaminho.get("icone") or "📜"
    st.session_state["ed_categoria"] = pergaminho.get("categoria") or ""
    st.session_state["ed_corpo"] = pergaminho.get("corpo") or ""
    st.session_state["ed_exemplo"] = pergaminho.get("exemplo") or ""
    st.session_state["ed_sinais"] = pergaminho.get("sinais") or ""
    st.session_state["ed_protecao"] = pergaminho.get("protecao") or ""
    st.session_state["_crime_prefill_id"] = pergaminho["id"]


def _formulario_editar(pergaminho):
    """Formulario de edicao de um exemplo, ja preenchido."""
    _preencher_campos_edicao(pergaminho)

    with st.form(f"form_editar_crime_{pergaminho['id']}"):
        titulo = st.text_input("Título do golpe", key="ed_titulo")
        icone = st.text_input("Ícone (um emoji)", key="ed_icone")
        categoria = st.text_input("Categoria", key="ed_categoria")
        corpo = st.text_area("Descrição do golpe", height=140, key="ed_corpo")
        exemplo = st.text_area(
            "Exemplo de mensagem", height=120, key="ed_exemplo"
        )
        sinais = st.text_area(
            "Sinais de alerta (um por linha)", height=120, key="ed_sinais"
        )
        protecao = st.text_area(
            "Como se proteger (um por linha)", height=120, key="ed_protecao"
        )
        salvar = st.form_submit_button("Salvar alterações")

    if salvar:
        if not titulo.strip() or not corpo.strip():
            st.error("O título e a descrição não podem ficar vazios.")
            return
        atualizar_conteudo(
            pergaminho["id"],
            titulo.strip(),
            corpo.strip(),
            icone.strip() or "📜",
            categoria.strip(),
            exemplo.strip(),
            sinais.strip(),
            protecao.strip(),
        )
        st.session_state.pop("crime_em_edicao", None)
        st.session_state.pop("_crime_prefill_id", None)
        for chave in ("ed_titulo", "ed_icone", "ed_categoria", "ed_corpo",
                      "ed_exemplo", "ed_sinais", "ed_protecao"):
            st.session_state.pop(chave, None)
        st.success("Exemplo atualizado.")
        st.rerun()


def render_gerenciar_crime():
    """Pagina de publicacao e edicao dos exemplos de crime.

    E o que a coordenacao usa: publica um golpe novo, edita um exemplo
    pre-colocado, ou inativa um que nao serve mais. Tudo o que aparece
    aqui vira pergaminho na pagina dos alunos.
    """
    st.markdown(
        _html(
            """
            <p class="ce-pixel">EXEMPLOS DE CRIMES DIGITAIS</p>
            <p class="ce-subtitulo">Publique um exemplo de golpe novo, edite um dos pré-colocados, ou tire da lista o que não serve mais. Tudo o que for publicado aqui aparece como pergaminho para o aluno.</p>
            """
        ),
        unsafe_allow_html=True,
    )

    st.subheader("Publicar um exemplo novo")
    _formulario_publicar()

    st.divider()
    st.subheader("Exemplos já publicados")

    pergaminhos = carregar_pergaminhos()
    if not pergaminhos:
        st.info("Nenhum exemplo publicado ainda.")
        return

    edicao = st.session_state.get("crime_em_edicao")
    if edicao is not None:
        alvo = next(
            (p for p in pergaminhos if p["id"] == edicao),
            None,
        )
        if alvo is not None:
            st.markdown("#### Editando: %s" % alvo.get("titulo", ""))
            _formulario_editar(alvo)
            st.divider()

    for pergaminho in pergaminhos:
        pid = pergaminho["id"]
        titulo = pergaminho.get("titulo") or ""
        icone = pergaminho.get("icone") or "📜"
        origem = pergaminho.get("origem") or "publicado"
        rotulo_origem = (
            "pré-colocado" if origem == "pre_colocado" else "publicado"
        )

        with st.expander(f"{icone}  {titulo}", expanded=False):
            st.caption("Origem: %s" % rotulo_origem)
            st.write(pergaminho.get("corpo") or "")
            if pergaminho.get("exemplo"):
                st.markdown("**Exemplo de mensagem**")
                st.code(pergaminho["exemplo"], language=None)
            sinais = texto_para_linhas(pergaminho.get("sinais") or "")
            if sinais:
                st.markdown("**Sinais de alerta**")
                for linha in sinais:
                    st.markdown("- %s" % linha)
            protecao = texto_para_linhas(pergaminho.get("protecao") or "")
            if protecao:
                st.markdown("**Como se proteger**")
                for linha in protecao:
                    st.markdown("- %s" % linha)

            col1, col2 = st.columns(2)
            if col1.button("Editar", key=f"editar_crime_{pid}"):
                st.session_state["crime_em_edicao"] = pid
                st.rerun()
            if col2.button("Inativar", key=f"inativar_crime_{pid}"):
                inativar_conteudo(pid)
                st.warning("Exemplo inativado. Ele não aparece mais para o aluno.")
                st.rerun()
