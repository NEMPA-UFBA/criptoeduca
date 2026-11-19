import streamlit as st 
import os
import io
import math
from PIL import Image

from modules.estilo import aplicar_css
from modules.senhas import tem_espaco, validar_forca_senha
# Importa módulos de renderização da UI
# Puxa do gerenciador de banco de dados otimizado as tarefas de atualização e leitura
from modules.database import (
    atualizar_perfil, obter_dados_perfil, atualizar_foto,
    buscar_usuarios, seguir_usuario, deixar_de_seguir, listar_seguidos,
)


# O CSS desta tela fica em static/css/perfil.css (ver aplicar_css em modules/estilo.py).

RAIZ_PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_AVATARES = os.path.join(RAIZ_PROJETO, "static", "avatares")
EXTENSOES = (".png", ".jpg", ".jpeg", ".webp")
PASTAS = {"Masculino": "masc", "Feminino": "fem"}
TAM_MINIATURA = 64
COLUNAS_GRADE = 3
POR_PAGINA = 6
TAM_AVATAR_SALVO = 128

@st.cache_data(show_spinner=False)
def listar_avatares(subpasta: str) -> tuple[str, ...]:
     """Lista nomes de arquivo (strings pequenas) e cacheia por subpasta."""
     pasta = os.path.join(BASE_AVATARES, subpasta)
     if not os.path.isdir(pasta):
         return ()
     return tuple(sorted(f for f in os.listdir(pasta) if f.lower().endswith(EXTENSOES)))
 
@st.cache_data(show_spinner=False, max_entries=200)
def gerar_miniatura(caminho: str, mtime: float) -> bytes:
    with Image.open(caminho) as img:
        img.draft("RGB", (TAM_MINIATURA * 2, TAM_MINIATURA * 2))  # o JPEG é decodificado já reduzido
        img = img.convert("RGB")
        img.thumbnail((TAM_MINIATURA, TAM_MINIATURA))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue()
def preparar_avatar(rel_path: str) -> bytes:
    with Image.open(os.path.join(BASE_AVATARES, rel_path)) as img:
        img.draft("RGB", (TAM_AVATAR_SALVO * 2, TAM_AVATAR_SALVO * 2))  # decodifica o JPEG já reduzido
        img = img.convert("RGB")
        img.thumbnail((TAM_AVATAR_SALVO, TAM_AVATAR_SALVO))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue()          # ~15–30 KB em vez de ~3 MB

# --- CALLBACKS DE ESTADO ---
# Toda ação que altera estado no banco/sessão agora usa callback para evitar st.rerun() solto e ghosting[cite: 3, 9]
def alternar_avatar(rel_path):
    if st.session_state.get("avatar_selecionado") == rel_path:
        st.session_state.pop("avatar_selecionado", None)
    else:
        st.session_state["avatar_selecionado"] = rel_path

def cancelar_selecao():
    st.session_state.pop("avatar_selecionado", None)


# Sem st.toast aqui, de proposito. Verificado no navegador: um toast chamado
# no callback de um botao DENTRO de um dialogo nao aparece (o Streamlit avisa
# que mostrar elementos nesse momento "nao e oficialmente suportado"). O
# retorno visual ja existe: "Seguir" vira "✓ Seguindo", e quem deixa de ser
# seguido sai da lista.
def _seguir(seguidor, seguido):
    seguir_usuario(seguidor, seguido)


def _deixar_de_seguir(seguidor, seguido):
    deixar_de_seguir(seguidor, seguido)

# O aviso vai por "toast_notificacao" e e mostrado pelo app.py, e nao com
# st.toast aqui: verificado no navegador, um toast chamado no callback de um
# botao dentro de um dialogo nao aparece. A chave e apagada pelo app.py logo
# que o toast e mostrado. O st.rerun() faz o app inteiro redesenhar (e nao so
# o dialogo), para a foto nova aparecer tambem na barra lateral.
def salvar_foto_callback(username, rel_path):
    atualizar_foto(username, preparar_avatar(rel_path))
    st.session_state.pop("avatar_selecionado", None)
    st.session_state["toast_notificacao"] = "Foto de perfil atualizada!"
    st.rerun()


def remover_foto_callback(username):
    atualizar_foto(username, None)
    st.session_state.pop("avatar_selecionado", None)
    st.session_state["toast_notificacao"] = "Foto de perfil removida!"
    st.rerun()

def seletor_avatar():
    if not os.path.isdir(BASE_AVATARES):
      st.error(f"Pasta não encontrada: {BASE_AVATARES}")
      return
 
    selecionado = st.session_state.get("avatar_selecionado")
    if selecionado:
        caminho_sel = os.path.join(BASE_AVATARES, selecionado)
        if os.path.isfile(caminho_sel):
            st.image(
                gerar_miniatura(caminho_sel, os.path.getmtime(caminho_sel)),
                caption="Novo avatar (salve para aplicar)",
                width=TAM_MINIATURA,
            )
 
    genero = st.segmented_control(
        "Gênero", list(PASTAS.keys()), default="Masculino",
        required=True, key="seg_genero", label_visibility="collapsed",
    )

    subpasta = PASTAS[genero]
    arquivos_disponiveis = listar_avatares(subpasta)
 
    if not arquivos_disponiveis:
        st.warning("Nenhum avatar encontrado nessa pasta.")
        return
 
    total_paginas = math.ceil(len(arquivos_disponiveis) / POR_PAGINA)
    pagina = 1
    if total_paginas > 1:
        pagina = st.number_input("Página", 1, total_paginas, 1, key=f"pag_{subpasta}")
    inicio = (pagina - 1) * POR_PAGINA
    pagina_arquivos = arquivos_disponiveis[inicio:inicio + POR_PAGINA]

    with st.container(key="grade_avatares"):
        for i in range(0, len(pagina_arquivos), COLUNAS_GRADE):
            colunas = st.columns(COLUNAS_GRADE)
            for coluna, arquivo in zip(colunas, pagina_arquivos[i:i + COLUNAS_GRADE]):
                caminho = os.path.join(BASE_AVATARES, subpasta, arquivo)
                rel = f"{subpasta}/{arquivo}"
                em_uso = (rel == selecionado)
                with coluna:
                    st.image(gerar_miniatura(caminho, os.path.getmtime(caminho)), width=TAM_MINIATURA)
                    st.button(
                        "✓ Em uso" if em_uso else "Usar",
                        key=f"btn_{rel}",
                        type="primary" if em_uso else "secondary",
                        on_click=alternar_avatar,
                        args=(rel,),
                    )

# --- RENDERIZAÇÃO DO WIDGET ---
@st.dialog("👤 Meu Perfil", width="large", on_dismiss=cancelar_selecao)
def render_widget_perfil():
    username_atual = st.session_state['username']
    aplicar_css("perfil.css")

    aba_perfil, aba_seguir = st.tabs(
        ["👤 Meu perfil", "🤝 Seguir usuários"],
        key="abas_widget_perfil",
        on_change="rerun",
    )
    if aba_perfil.open:
        with aba_perfil:
            _render_aba_perfil(username_atual)
    if aba_seguir.open:
        with aba_seguir:
            _render_aba_seguir(username_atual)


def _render_aba_perfil(username_atual):
    tipo_usuario = st.session_state.get('tipo_usuario', '')
    somente_leitura = tipo_usuario == 'Administrador'

    dados_atuais = obter_dados_perfil(username_atual)
    nome_atual, foto_bytes = dados_atuais if dados_atuais else ("", None)

    # Contêiner raiz com chave unívoca para forçar limpeza do DOM na transição
    with st.container(key="container_aba_perfil"):
        col_form, col_foto = st.columns([1, 2])

        if somente_leitura:
            with col_form:
                st.subheader("Dados Pessoais")
                st.write(f"**Nome:** {nome_atual or 'Não informado'}")
                st.write(f"**Perfil:** {tipo_usuario or 'Administrador'}")
                st.caption("O perfil da coordenação é somente leitura.")
            with col_foto:
                with st.container(key="moldura_avatar_perfil", width=94):
                    if foto_bytes:
                        st.image(foto_bytes, width=72)
                    else:
                        st.info("Nenhuma foto cadastrada.")
            return

        with col_form:
            with st.form("form_perfil"):
                st.subheader("Dados Pessoais")
                novo_nome = st.text_input("Nome", value=nome_atual)

                st.divider()
                st.subheader("🔒 Alteração de Senha")
                senha_atual = st.text_input("Senha Atual", type="password")
                # O formulário (st.form) só roda o script no envio, então não
                # dá para ter o checklist ao vivo do cadastro aqui. A regra
                # fica visível no "?" do campo, antes de a pessoa digitar.
                nova_senha = st.text_input(
                    "Nova Senha",
                    type="password",
                    help=(
                        "Mínimo de 6 caracteres, com letra maiúscula, letra "
                        "minúscula e número. Sem espaços."
                    ),
                )
                confirma_senha = st.text_input("Confirme", type="password")

                if st.form_submit_button("Salvar Modificações", type="primary"):
                    if nova_senha:
                        if not senha_atual:
                            st.error("Digite sua senha atual.")
                            st.stop()
                        if nova_senha != confirma_senha:
                            st.error("As novas senhas não coincidem.")
                            st.stop()
                        # Espaço na senha nova tem aviso próprio, antes da
                        # regra geral. A regra geral (validar_forca_senha) já recusava,
                        # mas com uma mensagem que listava tudo de uma vez, e a
                        # pessoa não sabia que o problema era o espaço. A senha
                        # é recusada, nunca "corrigida": tirar o espaço em
                        # silêncio gravaria uma senha diferente da digitada.
                        if tem_espaco(nova_senha):
                            st.error(
                                "A nova senha não pode ter espaços. Digite-a "
                                "sem espaço nenhum, nem no começo nem no fim."
                            )
                            st.stop()
                        if not validar_forca_senha(nova_senha):
                            st.error(
                                "A nova senha precisa ter no mínimo 6 caracteres, com "
                                "maiúscula, minúscula e número, sem espaços e com no máximo 72 bytes."
                            )
                            st.stop()

                    resultado = atualizar_perfil(
                        username_atual, nova_senha, senha_atual, novo_nome
                    )

                    if resultado == "senha_atual_incorreta":
                        st.error("Senha atual incorreta.")
                    elif resultado == "senha_nova_invalida":
                        # Só chega aqui se a checagem acima for removida ou
                        # contornada: o banco também recusa (ver
                        # atualizar_perfil em modules/database.py).
                        st.error(
                            "A nova senha precisa ter no mínimo 6 caracteres, com "
                            "maiúscula, minúscula e número, sem espaços e com no máximo 72 bytes."
                        )
                    else:
                        st.session_state['nome_usuario'] = novo_nome
                        st.success("Perfil atualizado!")
                        st.rerun()

        with col_foto:
            with st.container(key="moldura_avatar_perfil", width=94):
                if foto_bytes:
                    st.image(foto_bytes, width=72)
                else:
                    st.info("Nenhuma foto cadastrada.")

            # Abas para alternar entre galeria de avatares e remoção de avatar
            aba_change_foto, aba_remover_foto = st.tabs(["Galeria de avatares", "Remover Avatar"], key="abas_foto", on_change="rerun")
            if aba_change_foto.open:
                with aba_change_foto:
                    seletor_avatar()
                    avatar_pendente = st.session_state.get("avatar_selecionado")
                    st.button(
                        "Salvar foto",
                        key="btn_salvar_foto",
                        type="primary",
                        disabled=not avatar_pendente,
                        on_click=salvar_foto_callback,
                        args=(username_atual, avatar_pendente),
                    )

            if aba_remover_foto.open:
                with aba_remover_foto:
                    st.button(
                        "Remover foto atual",
                        key="btn_remover_foto",
                        disabled=not foto_bytes,
                        on_click=remover_foto_callback,
                        args=(username_atual,),
                    )

def _render_aba_seguir(username_atual):
    seguidos = listar_seguidos(username_atual)

    termo = st.text_input(
        "Buscar por nome ou username",
        type="search",
        live="300ms",
        placeholder="Digite pelo menos 2 letras",
    )
    resultados = buscar_usuarios(termo, excluir=username_atual)
    if len((termo or "").strip()) >= 2 and not resultados:
        st.caption("Nenhum usuário encontrado.")

    with st.container(key="resultados_seguir"):
        for username, nome, tipo, foto in resultados:
            ja_sigo = username in seguidos
            col_foto, col_info, col_botao = st.columns(
                [1, 6, 2], vertical_alignment="center"
            )
            if foto:
                col_foto.image(foto, width=40)
            else:
                col_foto.markdown("👤")
            col_info.markdown(f"**{nome}** · `{username}` · {tipo}")
            col_botao.button(
                "✓ Seguindo" if ja_sigo else "Seguir",
                key=f"seguir_{username}",
                disabled=ja_sigo,
                on_click=_seguir,
                args=(username_atual, username),
            )

    st.divider()
    st.subheader(f"Quem você segue ({len(seguidos)})")
    if not seguidos:
        st.caption("Você ainda não segue ninguém.")
        return

    st.markdown(" · ".join(f"`{u}`" for u in seguidos))
    alvo = st.selectbox(
        "Deixar de seguir:", seguidos, index=None, placeholder="Selecione"
    )
    st.button(
        "Deixar de seguir",
        disabled=alvo is None,
        on_click=_deixar_de_seguir,
        args=(username_atual, alvo),
    )
