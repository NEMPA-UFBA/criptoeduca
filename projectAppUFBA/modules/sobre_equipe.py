import base64
import hashlib
import html
import json
import logging
from pathlib import Path, PurePosixPath

import streamlit as st

from modules.estilo import aplicar_css, aplicar_estilo, html_bruto

logger = logging.getLogger(__name__)

_RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO_EQUIPE = _RAIZ / "dados" / "equipe.json"

# Única pasta de onde uma foto pode ser lida. Do campo "avatar" do equipe.json
# só o NOME do arquivo é aproveitado: "roberto.jpg", "..\\static\\fotos\\roberto.jpg"
# e "../static/fotos/roberto.jpg" dão todos em static/fotos/roberto.jpg. Sem esta
# trava, "../.streamlit/secrets.toml" viraria base64 na página e qualquer aluno
# logado leria os segredos no código-fonte do HTML. É o mesmo cuidado que
# leitura.py tem com os PDFs (_caminho_pdf_seguro).
PASTA_FOTOS = (_RAIZ / "static" / "fotos").resolve()

# Lista de permissão, não de proibição: só formatos de imagem conhecidos.
_TIPOS_IMAGEM = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

# Cores dos avatares de iniciais. A escolha é estável por nome (hash), então
# a mesma pessoa tem sempre a mesma cor.
_CORES_INICIAIS = ("#1E88E5", "#8E24AA", "#00897B", "#F4511E", "#3949AB", "#6D4C41")


def _formatar_horas(valor):
    if valor is None or valor == "":
        return "Não informado"
    horas = str(valor).strip()
    return horas if horas.lower().endswith("h") else f"{horas} h"


def _mtime(caminho):
    """Data de modificação do arquivo, ou 0 se ele não existir.

    Entra como ARGUMENTO das funções em cache. O st.cache_data não observa
    arquivos: a chave do cache é o código da função mais os argumentos. Passar
    o mtime faz o cache se renovar sozinho quando alguém troca a foto ou edita
    o JSON, sem precisar reiniciar o app.
    """
    try:
        return caminho.stat().st_mtime_ns
    except OSError:
        return 0


def _caminho_foto_seguro(valor_avatar):
    """Resolve o avatar dentro de PASTA_FOTOS, ou devolve None.

    URL externa (http/https) também cai em None: o avatar vira iniciais.
    """
    texto = str(valor_avatar or "").strip()
    if not texto or texto.lower().startswith(("http://", "https://")):
        return None
    # PurePosixPath(...).name descarta toda a parte de pastas, inclusive "..".
    # A barra invertida vira "/" antes, porque o JSON foi escrito no Windows e
    # o Streamlit Cloud roda em Linux, onde "\\" não separa pastas.
    nome = PurePosixPath(texto.replace("\\", "/")).name
    caminho = (PASTA_FOTOS / nome).resolve()
    # Segunda trava, para o caso de PASTA_FOTOS conter um atalho (symlink):
    # resolve() segue o atalho e is_relative_to confere que o destino final
    # ainda está dentro da pasta.
    if not caminho.is_relative_to(PASTA_FOTOS):
        logger.warning("Avatar fora da pasta de fotos recusado: %s", nome)
        return None
    if caminho.suffix.lower() not in _TIPOS_IMAGEM:
        logger.warning("Avatar com extensão não permitida recusado: %s", nome)
        return None
    if not caminho.is_file():
        logger.warning("Avatar local não encontrado: %s", caminho)
        return None
    return caminho


@st.cache_data(show_spinner=False, max_entries=32)
def _foto_em_data_uri(caminho_str, mtime_ns):
    """Lê a foto e devolve um data URI. Em cache: roda uma vez por arquivo.

    mtime_ns só existe para compor a chave do cache (ver _mtime). Atenção: ele
    NÃO pode começar com "_". No st.cache_data, parâmetro com "_" na frente é
    deixado de fora da chave, e o cache nunca perceberia a foto nova.
    """
    caminho = Path(caminho_str)
    tipo = _TIPOS_IMAGEM[caminho.suffix.lower()]
    codificado = base64.b64encode(caminho.read_bytes()).decode("ascii")
    return f"data:{tipo};base64,{codificado}"


def _avatar_iniciais(nome):
    """Avatar com as iniciais, gerado aqui mesmo como SVG.

    Substitui o ui-avatars.com: cada visita à página fazia o navegador do aluno
    pedir a imagem a um serviço de fora, levando o IP do aluno e o nome do
    membro. Num app que ensina LGPD (necessidade, segurança), dado que não
    precisa sair não sai.
    """
    partes = [p for p in str(nome or "").split() if p]
    iniciais = "".join(p[0] for p in partes[:2]).upper() or "?"
    indice = int(hashlib.sha256(str(nome).encode("utf-8")).hexdigest(), 16)
    cor = _CORES_INICIAIS[indice % len(_CORES_INICIAIS)]
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128">'
        f'<rect width="128" height="128" fill="{cor}"/>'
        '<text x="50%" y="50%" dy=".35em" text-anchor="middle" '
        'font-family="sans-serif" font-size="52" fill="#fff">'
        f"{html.escape(iniciais)}</text></svg>"
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def _avatar_src(membro):
    """Foto local validada; sem foto, as iniciais. Nunca uma URL externa."""
    caminho = _caminho_foto_seguro(membro.get("avatar"))
    if caminho is None:
        return _avatar_iniciais(membro.get("nome"))
    return _foto_em_data_uri(str(caminho), _mtime(caminho))


@st.cache_data(show_spinner=False, max_entries=4)
def _carregar_equipe(mtime_ns):
    """Lê o equipe.json uma vez por versão do arquivo."""
    with ARQUIVO_EQUIPE.open(encoding="utf-8") as arquivo:
        return json.load(arquivo)


def _card_equipe(membro):
    nome = html.escape(str(membro.get("nome", "Membro da equipe")), quote=True)
    funcao = html.escape(str(membro.get("funcao", "")), quote=True)
    horas = html.escape(_formatar_horas(membro.get("horas")), quote=True)
    resumo = html.escape(str(membro.get("resumo", "")), quote=True)
    avatar = html.escape(_avatar_src(membro), quote=True)

    return html_bruto(f"""
    <div class="ce-card" style="min-height: 0; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);">
      <img src="{avatar}" alt="Avatar de {nome}" style="width: 88px; height: 88px; border-radius: 50%; object-fit: cover; border: 2px solid rgba(56, 189, 248, 0.45);">
      <p class="ce-titulo">{nome}</p>
      <p style="color: #7dd3fc; font-size: 0.92rem; font-weight: 600; margin: 0;">{funcao}</p>
      <span class="ce-badge" style="width: fit-content;">⏱️ {horas}</span>
      <p class="ce-resumo">{resumo}</p>
    </div>
    """)


def _diario_do_membro(membro, indice):
    """Registros do diário de bordo, se o membro tiver algum no JSON.

    Formato opcional em equipe.json:
        "diario": [{"data": "17/11/2026", "atividade": "..."}]
    st.markdown com texto escapado em vez de HTML: o texto vem do JSON, e
    escapar é o que impede um registro de virar código na página.
    """
    registros = membro.get("diario")
    if not isinstance(registros, list) or not registros:
        return
    with st.expander(f"📓 Diário de bordo ({len(registros)})", key=f"diario_membro_{indice}"):
        for registro in registros:
            if not isinstance(registro, dict):
                continue
            data = html.escape(str(registro.get("data", "")))
            atividade = html.escape(str(registro.get("atividade", "")))
            st.markdown(f"**{data}** — {atividade}")


def render_sobre_equipe():
    """Exibe a equipe do projeto e o diário resumido de atividades."""
    aplicar_estilo()
    # A key do contêiner dá um alvo estável para o CSS da página, sem depender
    # da key que app.py gera a partir do rótulo do menu.
    aplicar_css("equipe.css")
    with st.container(key="equipe_diario"):
        st.title("👥 Equipe e Diário de Bordo")
        st.write("Conheça as pessoas do projeto e acompanhe suas contribuições.")

        try:
            equipe = _carregar_equipe(_mtime(ARQUIVO_EQUIPE))
        except (OSError, json.JSONDecodeError):
            logger.exception("Falha ao carregar os dados da equipe em %s", ARQUIVO_EQUIPE)
            st.error("Não foi possível carregar os dados da equipe.")
            return

        if not isinstance(equipe, list):
            logger.error("O arquivo de equipe deve conter uma lista: %s", ARQUIVO_EQUIPE)
            st.error("Os dados da equipe estão em um formato inválido.")
            return

        for inicio in range(0, len(equipe), 2):
            colunas = st.columns(2)
            for deslocamento, (coluna, membro) in enumerate(
                zip(colunas, equipe[inicio : inicio + 2])
            ):
                if not isinstance(membro, dict):
                    logger.warning("Registro de membro inválido em %s", ARQUIVO_EQUIPE)
                    continue
                with coluna:
                    st.markdown(_card_equipe(membro), unsafe_allow_html=True)
                    _diario_do_membro(membro, inicio + deslocamento)
