import streamlit as st 
import os
import io
import math
from PIL import Image
# Importa módulos de renderização da UI
# Puxa do gerenciador de banco de dados otimizado as tarefas de atualização e leitura
from modules.database import atualizar_perfil, obter_dados_perfil, buscar_usuarios, seguir_usuario, atualizar_foto


CSS_GRADE = """
<style>
/* miniaturas: cantos arredondados e borda discreta no tom do painel */
.st-key-grade_avatares img {
    border-radius: 10px;
    border: 2px solid #24334a;
    transition: border-color 0.2s ease, transform 0.2s ease;
}
.st-key-grade_avatares img:hover {
    border-color: #4F46E5;
    transform: translateY(-2px);
}
/* avatar escolhido: borda ciano com brilho, igual à moldura */
.st-key-grade_avatares [class*="_ativo"] img {
    border-color: #38bdf8;
    box-shadow: 0 0 10px rgba(56, 189, 248, 0.5);
}
/* botões "Usar" baixinhos */
.st-key-grade_avatares button {
    min-height: 1.5rem;
    padding: 0 0.3rem;
    font-size: 0.72rem;
}
.st-key-grade_avatares [data-testid="stElementToolbar"] {
    display: none;
}
@media (prefers-reduced-motion: reduce) {
    .st-key-grade_avatares img { transition: none; }
}
</style>
"""

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
def acao_seguir_callback(seguidor, seguido):
    seguir_usuario(seguidor, seguido)
    st.session_state["toast_notificacao"] = f"Você começou a seguir {seguido}!" # Define notificação via flag

def selecionar_avatar(rel_path):
    st.session_state["avatar_selecionado"] = rel_path
    st.session_state["remover_foto"] = False

def validar_forca_senha(senha):
    tem_maiuscula = any(c.isupper() for c in senha)
    tem_minuscula = any(c.islower() for c in senha)
    tem_numero = any(c.isdigit() for c in senha)
    return tem_maiuscula and tem_minuscula and tem_numero

def salvar_foto_callback(username, rel_path):
    atualizar_foto(username, preparar_avatar(rel_path))
    st.session_state.pop("avatar_selecionado", None)
    st.session_state["toast_notificacao"] = "Foto de perfil atualizada!" # Define notificação via flag
    st.rerun()
 
def remover_foto_callback(username):
    atualizar_foto(username, None)
    st.session_state.pop("avatar_selecionado", None)
    st.session_state["toast_notificacao"] = "Foto de perfil removida!" # Define notificação via flag
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
                    on_click=selecionar_avatar,
                    args=(rel,),
                )
def marcar_remocao():
    st.session_state["avatar_selecionado"] = None
    st.session_state["remover_foto"] = True

# --- RENDERIZAÇÃO DO WIDGET ---
@st.dialog("⚙️ Editar Perfil e Buscar Comunidade", width="large") # Transforma e dimensiona a função como janela modal larga e fixa

def render_widget_perfil(): # Define a renderização do conteúdo de sobreposição
    username_atual = st.session_state['username']
    
    # Busca dados estritamente transacional sem onerar a inicialização do app
    dados_atuais = obter_dados_perfil(username_atual)
    nome_atual, foto_bytes = dados_atuais if dados_atuais else ("", None)

    aba_perfil, aba_pesquisa = st.tabs(["Meu Perfil", "Buscar Usuários"], key="abas_perfil", on_change="rerun")
    if aba_perfil.open:
        with aba_perfil:
            st.html(CSS_GRADE)
             # Contêiner raiz com chave unívoca para forçar limpeza do DOM na transição
            with st.container(key="container_aba_perfil"):
                col_form, col_foto = st.columns([1, 2])
                
            with col_form:
                 with st.form("form_perfil"):
                    st.subheader("Dados Pessoais")
                    novo_nome = st.text_input("Nome", value=nome_atual)
                    
                    st.divider()
                    st.subheader("🔒 Alteração de Senha")
                    senha_atual = st.text_input("Senha Atual", type="password")
                    nova_senha = st.text_input("Nova Senha", type="password")
                    confirma_senha = st.text_input("Confirme", type="password")
                    
                    if st.form_submit_button("Salvar Modificações", type="primary"):
                        if nova_senha:
                            if not senha_atual:
                                st.error("Digite sua senha atual.")
                                st.stop()
                            if nova_senha != confirma_senha:
                                st.error("As novas senhas não coincidem.")
                                st.stop()
                            if not validar_forca_senha(nova_senha):
                                st.error("A nova senha precisa de maiúscula, minúscula e número.")
                                st.stop()

                        resultado = atualizar_perfil(
                            username_atual, nova_senha, senha_atual, novo_nome
                        )

                        if resultado == "senha_atual_incorreta":
                            st.error("Senha atual incorreta.")
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

                #Criação de abas para alternar entre galeria de avatares e remoção de avatar
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
                    if st.session_state.get("remover_foto"):
                        st.warning("A foto será removida ao salvar as modificações.")

    if aba_pesquisa.open:                        
        with aba_pesquisa:
        # Segundo contêiner isolado para gerenciar a memória e o layout de forma independente[cite: 3, 9]
          with st.container(key="container_aba_pesquisa"):
            termo = st.text_input("Buscar perfis por nome:")
            
            if st.button("Buscar"):
                if termo:
                    resultados = buscar_usuarios(termo)
                    if resultados:
                        for username_encontrado, nome_user, tipo_user in resultados:
                            # Ignora o próprio usuário na lista de resultados
                            if username_encontrado == username_atual:
                                continue
                                
                            col_info, col_btn = st.columns([3, 1])
                            with col_info:
                                st.info(f"👤 **{nome_user}** | 🏷️ {tipo_user}")
                            with col_btn:
                                # Elemento iterável requer argumento 'key' parametrizado e unívoco[cite: 9]
                                # A mutação de seguir é feita via callback (on_click) para máxima fluidez[cite: 3, 9]
                                st.button(
                                    "Seguir",
                                    key=f"btn_seguir_{username_encontrado}",
                                    type="secondary",
                                    use_container_width=True,
                                    on_click=acao_seguir_callback,
                                    args=(username_atual, username_encontrado)
                                )
                    else:
                        st.warning("Nenhum usuário encontrado.")