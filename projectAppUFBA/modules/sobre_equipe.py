import html
import json
import logging
from pathlib import Path

import streamlit as st

from modules.estilo import aplicar_css, aplicar_estilo, html_bruto

logger = logging.getLogger(__name__)
ARQUIVO_EQUIPE = Path(__file__).resolve().parent.parent / "dados" / "equipe.json"


def _formatar_horas(valor):
    if valor is None or valor == "":
        return "Não informado"
    horas = str(valor).strip()
    return horas if horas.lower().endswith("h") else f"{horas} h"


def _card_equipe(membro):
    nome = html.escape(str(membro.get("nome", "Membro da equipe")), quote=True)
    funcao = html.escape(str(membro.get("funcao", "")), quote=True)
    horas = html.escape(_formatar_horas(membro.get("horas")), quote=True)
    resumo = html.escape(str(membro.get("resumo", "")), quote=True)
    avatar = html.escape(str(membro.get("avatar", "")), quote=True)

    return html_bruto(f"""
    <div class="ce-card" style="min-height: 0; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);">
      <img src="{avatar}" alt="Avatar de {nome}" style="width: 88px; height: 88px; border-radius: 50%; object-fit: cover; border: 2px solid rgba(56, 189, 248, 0.45);">
      <p class="ce-titulo">{nome}</p>
      <p style="color: #7dd3fc; font-size: 0.92rem; font-weight: 600; margin: 0;">{funcao}</p>
      <span class="ce-badge" style="width: fit-content;">⏱️ {horas}</span>
      <p class="ce-resumo">{resumo}</p>
    </div>
    """)


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
            with ARQUIVO_EQUIPE.open(encoding="utf-8") as arquivo:
                equipe = json.load(arquivo)
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
            for coluna, membro in zip(colunas, equipe[inicio : inicio + 2]):
                if not isinstance(membro, dict):
                    logger.warning("Registro de membro inválido em %s", ARQUIVO_EQUIPE)
                    continue
                with coluna:
                    st.markdown(_card_equipe(membro), unsafe_allow_html=True)
