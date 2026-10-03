import streamlit as st
import random
import html
from modules.database import atualizar_primeiro_acesso, salvar_mensagem_mural, carregar_mural, inativar_mensagem_mural
def gerar_cifra_usuario(username):
    """Gera um dicionário de substituição único e fixo baseado no username do usuário"""
    caracteres_originais = list("abcdefghijklmnopqrstuvwxyz0123456789 .,!?")
    caracteres_embaralhados = list(caracteres_originais)
    
    seed_numerica = sum(ord(c) for c in username)
    rng = random.Random(seed_numerica)
    rng.shuffle(caracteres_embaralhados)
    
    mapa = {orig: emb for orig, emb in zip(caracteres_originais, caracteres_embaralhados)}
    return mapa

def criptografar_texto(texto, username):
    mapa = gerar_cifra_usuario(username)
    resultado = []
    for char in texto.lower():
        resultado.append(mapa.get(char, char))
    return "".join(resultado)

def render_sessao_interativa(modo_voluntario=False):
    username_atual = st.session_state["username"]
    # --- CSS CUSTOMIZADO PARA A TEMÁTICA DE CRIPTOGRAFIA ---
    st.markdown("""
        <style>
        /* Caixa de destaque da Chave de Criptografia */
        .cifra-box {
            background: linear-gradient(135deg, rgba(79, 70, 229, 0.1), rgba(15, 23, 42, 0.2));
            border: 1px solid rgba(79, 70, 229, 0.3);
            padding: 1.5rem;
            border-radius: 12px;
            margin-bottom: 1.5rem;
        }
        
        /* Estilização dos blocos do mural e caixas de texto */
        .stTextArea textarea {
            background-color: #0f172a !important;
            color: #f8fafc !important;
            border: 1px solid #334155 !important;
            border-radius: 8px !important;
        }
        
        /* Efeito visual para as mensagens cifradas no mural */
        .mural-item {
            background-color: rgba(30, 41, 59, 0.4);
            border-left: 4px solid #4F46E5;
            padding: 1rem;
            border-radius: 0 8px 8px 0;
            margin-bottom: 0.75rem;
            font-family: monospace;
        }
        </style>
    """, unsafe_allow_html=True)
    
    if modo_voluntario:
        if st.button("⬅️ Voltar para o Menu Principal"):
            st.session_state["voltar_para_menu"] = True
            st.rerun()

    st.title("🎯 Sessão Interativa: Mural Criptografado e Anônimo")
    
    # EXIBE A CIFRA DO USUÁRIO QUANDO ACESSADO DO SEGUNDO LOGIN EM DIANTE (OU VOLUNTARIAMENTE)
    if modo_voluntario or st.session_state.get("primeiro_acesso") == 0:
        st.info("🔐 Esta é a sua **chave de substituição pessoal e fixa** associada à sua conta. Ela é usada para cifrar e decifrar suas mensagens no mural.")
        
        mapa_usuario = gerar_cifra_usuario(username_atual)
        
        # Exibe o mapeamento completo de forma limpa em colunas ou expansor
        with st.expander("🔍 Ver o dicionário completo da sua Cifra Individual", expanded=False):
            st.write("Cada caractere original à esquerda corresponde ao caractere cifrado à direita:")
            
            # Formata o dicionário em uma tabela ou lista legível
            cols = st.columns(4)
            itens = list(mapa_usuario.items())
            chunk_size = len(itens) // 4 + 1
            
            for i, col in enumerate(cols):
                with col:
                    sub_itens = itens[i * chunk_size : (i + 1) * chunk_size]
                    for orig, cif in sub_itens:
                        exibir_orig = "Espaço" if orig == " " else orig
                        st.markdown(f"`{exibir_orig}` ➔ **`{cif}`**")

    with st.form("form_mural_interativo"):
        mensagem = st.text_area("Digite sua mensagem secreta para o mural:")
        btn_enviar = st.form_submit_button("Criptografar com sua Chave e Enviar")

        if btn_enviar:
            if mensagem.strip():
                msg_cifrada = criptografar_texto(mensagem, username_atual)
                # A funcao pede dois argumentos: quem mandou e o que mandou.
                # Sem o username o INSERT fica sem autor e a mural nunca
                # guardou nada, porque o TypeError matava o script aqui.
                salvar_mensagem_mural(username_atual, msg_cifrada)
                
                if st.session_state.get("primeiro_acesso") == 1:
                    atualizar_primeiro_acesso(username_atual)
                    st.session_state["primeiro_acesso"] = 0
                
                st.session_state["mostrar_explicacao"] = True
                st.rerun()
            else:
                st.error("Escreva alguma mensagem antes de enviar.")
    st.markdown("---")
    st.subheader("📌 Mural de Mensagens Públicas Cifradas")
    
    tipo_usuario = st.session_state.get("tipo_usuario", "Aluno")
    eh_gestor = tipo_usuario in ["Professor", "Administrador"]

    mensagens = carregar_mural()
    
    if mensagens:
        for msg_id, autor_msg, msg, data in mensagens:
            col_msg, col_botoes = st.columns([4, 1])
            
            with col_msg:
                # A mensagem entra em HTML cru, entao precisa de escape. A
                # cifra nao cobre "<" nem ">": o alfabeto dela e so letras,
                # numeros e " .,!?", e o mapa usa mapa.get(char, char), que
                # devolve qualquer caractere fora do alfabeto sem trocar.
                # Como a cifra e uma permutacao, da para digitar as letras
                # pre-imagem e forjar uma tag no meio do mural.
                st.markdown(f"""
                    <div class="mural-item">
                        <span style="color: #94a3b8; font-size: 0.85rem;">🕒 {data}</span><br>
                        <span style="color: #38bdf8; font-size: 1.1rem; font-weight: bold;">{html.escape(msg)}</span>
                    </div>
                """, unsafe_allow_html=True)
                
            with col_botoes:
                # O próprio autor pode limpar/excluir a sua mensagem
                if autor_msg == username_atual:
                    if st.button("🗑️ Limpar Minha", key=f"limpar_{msg_id}", type="secondary"):
                        inativar_mensagem_mural(msg_id)
                        st.success("Sua mensagem foi removida!")
                        st.rerun()
                
                # Professores e Admins podem inativar qualquer mensagem do mural
                if eh_gestor and autor_msg != username_atual:
                    if st.button("🛡️ Inativar", key=f"gestor_del_{msg_id}", type="secondary"):
                        inativar_mensagem_mural(msg_id)
                        st.warning(f"Mensagem {msg_id} inativada pela moderação.")
                        st.rerun()
    else:
        st.info("Nenhuma mensagem no mural ainda. Seja o primeiro a publicar!")