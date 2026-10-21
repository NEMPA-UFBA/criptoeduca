"""Folha de estilo da identidade visual do CriptoEduca.

O CSS do app estava espalhado: app.py, modules/login.py e
modules/sessaoInterativa.py escreviam as mesmas cores em lugares diferentes.
Isso não é só bagunça -- é o que produz a inconsistência de hover e de
override que cada um dos arquivos tentava consertar por conta própria. Por
isso a paleta fica aqui, num lugar só, e as páginas pedem o que precisam.

A paleta é a que o login e o mural já usavam, então o app não muda de cor
nenhuma: fundo #0f172a, painel #1e293b, roxo #4F46E5, ciano #38bdf8.

A fonte Press Start 2P é usada só em títulos. Ela é pixelada e tem avanço
de 1em por caractere: em texto corrido ela fica ilegível, e o próprio app.py
já restringe o uso dela aos h1. Aqui a regra é a mesma.

Sobre o HTML: o Streamlit passa o texto do st.markdown pelo interpretador de
Markdown antes de entregar ao navegador. Duas coisas quebram com HTML
cru, e as duas apareceram na verificação no navegador:

  1. Linha começando com 4 espaços vira bloco de código. A indentação do
     próprio arquivo Python contam.
  2. Linha em branco no meio do HTML encerra o bloco HTML e o resto volta
     a ser Markdown -- aí sobra um "</div>" escrito na tela.

Por isso os trechos de HTML do app são montados sem indentação e sem linha
em branco. Ver _html() em modules/mainmenu.py.
"""

import streamlit as st

# Cores da identidade. Nomeadas para não repetir o literal hex em dois
# lugares e acabar divergindo.
FUNDO = "#0f172a"
PAINEL = "#1e293b"
PAINEL_ALTO = "#24334a"
ROXO = "#4F46E5"
CIANO = "#38bdf8"
AMBAR = "#f59e0b"
VERDE = "#22c55e"
TEXTO = "#e2e8f0"
TEXTO_FRACO = "#94a3b8"

CSS_IDENTIDADE = """
<style>
/* ---------- Título em pixel ---------- */
/* Os seletores de texto levam .stMarkdown na frente porque o Streamlit
   escreve ".stMarkdown p { font-size: ... }", que tem especificidade
   (0,1,1) e ganha de um ".ce-pixel" sozinho (0,1,0). Sem esse prefixo o
   título saía com 16px em vez do tamanho escolhido -- foi o que apareceu
   na verificação no navegador. */
.stMarkdown p.ce-pixel {
    font-family: "PressStart2P", monospace;
    font-weight: 400;
    font-size: 26px;
    line-height: 1.5;
    letter-spacing: 0;
    -webkit-font-smoothing: none;
    color: #f1f5f9;
    margin: 0 0 0.35rem 0;
}
/* A Press Start 2P só tem o peso 400. Pedir 700 faz o navegador inventar um
   negrito falso, que borra os pixels e desfaz o efeito. */
.stMarkdown p.ce-subtitulo {
    color: #94a3b8;
    font-size: 0.98rem;
    margin: 0 0 1.6rem 0;
    max-width: 60ch;
}

/* ---------- Card de módulo ---------- */
/* O Streamlit monta a coluna com align-items: start, o que faz cada
   elemento encolher até a largura do próprio conteúdo. Medido: o card
   ficava com 124px dentro de uma coluna de 166px. A regra abaixo estica
   o bloco vertical dos containers que têm key "card_*" -- o seletor usa a
   classe "st-key-card_..." que o app mesmo cria pelo key= do st.container.
   A classe fica no MESMO elemento do stVerticalBlock, e não acima dele:
   por isso o seletor é ".stVerticalBlock[class*=...]" e não
   "[class*=...] [data-testid=...]" -- este último não casava com nada. */
.stVerticalBlock[class*="st-key-card_"] {
    align-items: stretch;
}
/* O Streamlit escreve "width: fit-content" no container de cada elemento
   (classe de emotion, sem nome estável). Com fit-content, o item do flex
   não estica: o card ficava com a largura do texto -- medido, 124px
   dentro de uma coluna de 166px. Por isso o width: 100% aqui. */
.stVerticalBlock[class*="st-key-card_"] [data-testid="stElementContainer"],
.stVerticalBlock[class*="st-key-card_"] [data-testid="stMarkdownContainer"] {
    width: 100%;
}
/* ---------- Cards de mesma altura na fileira ----------
   Sem isto, os botões da fileira ficam em alturas diferentes: medido, os
   três primeiros botões em 872, 870 e 806px de topo, porque o card do
   Phishing tem resumo mais curto.

   A cadeia é: a coluna (stColumn) -> bloco vertical -> stLayoutWrapper ->
   bloco vertical do container (o que tem a classe st-key-card_). Cada
   degrau precisa esticar a altura, senão o card mais baixo não sabe que
   existe um irmão mais alto na mesma fileira. */
[data-testid="stColumn"] > [data-testid="stVerticalBlock"] {
    align-items: stretch;
}
[data-testid="stColumn"] [data-testid="stLayoutWrapper"] {
    height: 100%;
}
.stVerticalBlock[class*="st-key-card_"] {
    height: 100%;
    display: flex;
    flex-direction: column;
}
/* O card ocupa o espaço que sobrar e o botão desce para o fundo. */
.stVerticalBlock[class*="st-key-card_"] .ce-card {
    flex: 1 1 auto;
}
.stVerticalBlock[class*="st-key-card_"] button {
    margin-top: auto;
}
.ce-card {
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: 14px;
    background: linear-gradient(160deg, rgba(30, 41, 59, 0.95), rgba(15, 23, 42, 0.95));
    padding: 1rem 1.1rem 1.1rem 1.1rem;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
    /* Altura mínima igual para todos os cards. É ela que alinha os botões
       da fileira. Com altura fixa (height) no container, o conteúdo mais
       longo abria uma barra de rolagem dentro do card -- por isso
       min-height, e não height.

       O valor 380px é o pior caso medido na janela estreita (coluna de
       166px), onde o card mais alto do manifesto ocupava 380px. Numa tela
       grande a coluna é bem mais larga, o conteúdo é mais curto, e é o
       min-height que mantém tudo alinhado. */
    min-height: 380px;
}
/* A faixa colorida no topo do card é a "cor do módulo". */
.ce-card-topo {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.6rem;
}
.ce-icone {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2.7rem;
    height: 2.7rem;
    border-radius: 12px;
    background: rgba(79, 70, 229, 0.16);
    border: 1px solid rgba(79, 70, 229, 0.35);
    font-size: 1.3rem;
    line-height: 1;
    flex-shrink: 0;
}
.stMarkdown p.ce-titulo {
    color: #f1f5f9;
    font-size: 1.06rem;
    font-weight: 700;
    line-height: 1.3;
    margin: 0;
}
.stMarkdown p.ce-resumo {
    color: #cbd5e1;
    font-size: 0.88rem;
    line-height: 1.5;
    margin: 0;
    flex-grow: 1;
}
.ce-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin-top: 0.2rem;
}
.ce-badge {
    display: inline-block;
    background: rgba(56, 189, 248, 0.12);
    border: 1px solid rgba(56, 189, 248, 0.30);
    color: #7dd3fc;
    border-radius: 999px;
    padding: 0.16rem 0.6rem;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.02em;
    white-space: nowrap;
}
.ce-badge-nivel {
    background: rgba(245, 158, 11, 0.12);
    border-color: rgba(245, 158, 11, 0.32);
    color: #fcd34d;
}
/* Selo de módulo concluído. */
.ce-badge-ok {
    background: rgba(34, 197, 94, 0.14);
    border-color: rgba(34, 197, 94, 0.35);
    color: #86efac;
}

/* ---------- Barra de progresso ---------- */
.ce-progresso-caixa {
    border: 1px solid rgba(79, 70, 229, 0.28);
    border-radius: 14px;
    background: linear-gradient(135deg, rgba(79, 70, 229, 0.14), rgba(15, 23, 42, 0.30));
    padding: 0.9rem 1.1rem;
    margin-bottom: 1.6rem;
}
.ce-progresso-topo {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.8rem;
    margin-bottom: 0.5rem;
    flex-wrap: wrap;
}
.ce-progresso-titulo {
    color: #f1f5f9;
    font-weight: 700;
    font-size: 0.95rem;
}
.ce-progresso-fracao {
    color: #94a3b8;
    font-size: 0.85rem;
}
.ce-progresso-trilho {
    height: 10px;
    border-radius: 999px;
    background: rgba(15, 23, 42, 0.85);
    border: 1px solid rgba(148, 163, 184, 0.20);
    overflow: hidden;
}
.ce-progresso-barra {
    height: 100%;
    border-radius: 999px;
    background: linear-gradient(90deg, #4F46E5, #38bdf8);
    transition: width 0.4s ease;
}

/* ---------- Cabeçalho da página do módulo ---------- */
.ce-modulo-cabecalho {
    border: 1px solid rgba(148, 163, 184, 0.16);
    border-left: 4px solid var(--ce-cor-modulo, #4F46E5);
    border-radius: 12px;
    background: rgba(30, 41, 59, 0.55);
    padding: 1.1rem 1.2rem;
    margin-bottom: 1.4rem;
}
.ce-modulo-cabecalho h2 {
    margin: 0 0 0.4rem 0;
    color: #f1f5f9;
    font-size: 1.35rem;
}
.ce-modulo-cabecalho p {
    margin: 0;
    color: #cbd5e1;
    font-size: 0.95rem;
    line-height: 1.55;
}
.ce-modulo-cabecalho .ce-tags {
    margin-top: 0.7rem;
}

/* ---------- Utilidades ---------- */
.ce-aviso {
    border: 1px dashed rgba(245, 158, 11, 0.45);
    background: rgba(245, 158, 11, 0.08);
    color: #fcd34d;
    border-radius: 12px;
    padding: 0.85rem 1rem;
    font-size: 0.9rem;
    line-height: 1.5;
}
.stMarkdown p.ce-aviso {
    margin: 0;
}

/* Quem pede menos animação não recebe transição */
@media (prefers-reduced-motion: reduce) {
    .ce-progresso-barra {
        transition: none;
    }
}

/* Em tela estreita (celular de aluno) os badges e o cabeçalho encolhem em
   vez de estourar a largura. */
@media (max-width: 640px) {
    .stMarkdown p.ce-pixel {
        font-size: 19px;
    }
    .ce-card {
        padding: 0.85rem 0.9rem 1rem 0.9rem;
    }
}
</style>
"""


def aplicar_estilo():
    """Injeta a folha de estilo da identidade na página."""
    st.markdown(CSS_IDENTIDADE, unsafe_allow_html=True)


def html_bruto(trecho):
    """Deixa um trecho de HTML pronto para o interpretador de Markdown.

    O Streamlit passa o texto do st.markdown pelo Markdown antes de mandar
    ao navegador, e HTML cru tem duas armadilhas:

      - linha começando com 4 espaços vira bloco de código (a indentação do
        próprio arquivo Python conta);
      - linha em branco no meio do HTML encerra o bloco HTML, e o resto
        volta a ser Markdown -- sobrando um "</div>" escrito na tela.

    As duas apareceram na verificação no navegador. Por isso este função
    tira a indentação e remove as linhas em branco.
    """
    linhas = [linha.strip() for linha in trecho.strip().splitlines()]
    return "\n".join(linha for linha in linhas if linha)
