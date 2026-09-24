import streamlit as st
import re
import random
from datetime import datetime
from modules.database import verificar_login, cadastrar_usuario

def validar_email_formato(email):
    """Valida se o e-mail tem um formato padrão (ex: usuario@dominio.com)."""
    padrao = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return bool(re.fullmatch(padrao, email))

def validar_forca_senha(senha):
    """Garante que a senha tenha pelo menos 1 letra maiúscula, 1 minúscula e 1 número."""
    tem_maiuscula = any(c.isupper() for c in senha)
    tem_minuscula = any(c.islower() for c in senha)
    tem_numero = any(c.isdigit() for c in senha)
    
    return tem_maiuscula and tem_minuscula and tem_numero

def obter_chave_professor_diaria(segredo_sistema="chaveDev2026"):
    """
    Gera uma chave numérica aleatória de 6 dígitos válida por 24h.
    Usa a data atual (YYYY-MM-DD) + segredo do sistema como semente.
    """
    data_hoje = datetime.now().strftime("%Y-%m-%d")
    semente = f"{segredo_sistema}_{data_hoje}"
    
    # Instancia um gerador aleatório isolado com a semente do dia
    gerador = random.Random(semente)
    
    # Gera um número fixo de 6 dígitos para o dia de hoje
    return str(gerador.randint(100000, 999999))

def render_admin():
    # Dupla verificação de segurança
    if st.session_state.get("tipo_usuario") != "Administrador":
        st.error("🚫 Acesso negado! Apenas administradores podem visualizar esta página.")
        return

    st.title("🛡️ Painel da Administração e Coordenação")
    st.write(f"Bem-vindo(a), **{st.session_state.get('nome_usuario')}**!")

    st.divider()

    # Exibição Restrita da Chave Diária
    st.subheader("🔑 Chave de Acesso para Novos Professores")
    st.write("Esta chave é gerada automaticamente a cada 24 horas. Repasse-a aos novos professores.")

    chave_hoje = obter_chave_professor_diaria()

    col1, col2 = st.columns([1, 2])
    with col1:
        st.metric(label="Chave Válida Hoje", value=chave_hoje)
    with col2:
        st.info("💡 A chave expira automaticamente às 23:59:59 de hoje.")

def render_login():

    st.markdown(""" 
    <style>
     /* Centralização do conteúdo no topo */
        .block-container {
            padding-top: 3rem;
            padding-bottom: 2rem;
            max-width: 900px;
        }
        [data-testid="stForm"] {
            background-color: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 2rem;
            box-shadow: 0px 10px 15px -3px rgba(0, 0, 0, 0.05);
        }
        /* Cabeçalho da área de login */
        .login-title {
            text-align: center;
            font-size: 28px;
            font-weight: 700;
            color: #1e293b;
            margin-bottom: 0.5rem;
        }
        .login-subtitle {
            text-align: center;
            font-size: 14px;
            color: #64748b;
            margin-bottom: 1.5rem;
        }

        /* Customização dos botões do formulário */
        div.stButton > button {
            width: 100%;
            background-color: #4F46E5;
            color: white;
            font-weight: 600;
            border-radius: 8px;
            border: none;
            padding: 0.5rem 1rem;
            transition: background-color 0.2s;
        }
        div.stButton > button:hover {
            background-color: #4338CA;
            color: white;
        }
    """, unsafe_allow_html=True)
    
    st.title("Acesso à Plataforma Educativa")
    aba_login, aba_cadastro = st.tabs(["Entrar", "Criar Conta"])
    with aba_login:
       with st.form("form_login"):
                usuario_input = st.text_input("Usuário")
                senha_input = st.text_input("Senha", type="password")
                btn_entrar = st.form_submit_button("Entrar")

                if btn_entrar:
                    # Envia o que foi digitado no container para a checagem no banco
                    nome_usuario = verificar_login(usuario_input, senha_input)

                    if nome_usuario:
                        st.session_state["usuario_logado"] = True
                        st.session_state["nome_usuario"] = nome_usuario
                        st.session_state["username"] = usuario_input
                        st.success("Login efetuado com sucesso!")
                        st.rerun()  # Recarrega a página para entrar no sistema[cite: 1]
                    else:
                        st.error("Usuário ou senha incorretos.") 

    with aba_cadastro:
            # Obtém a chave válida para o dia de hoje
       chave_valida_hoje = obter_chave_professor_diaria()
       with st.form("form_cadastro"):
                nome_input = st.text_input("Nome Completo")
                novo_usuario_input = st.text_input("Nome de Usuário")
                
                tipo_usuario_input = st.selectbox("Perfil de Acesso", ["Aluno", "Professor"])
                
                # Campo da chave de verificação
                chave_prof_input = st.text_input(
                    "Chave de Verificação de 6 dígitos (Apenas para Professores)", 
                    type="password",
                    help="Solicite a chave diária à coordenação."
                )

                email_input = st.text_input("E-mail")
                email_confirm_input = st.text_input("Confirme o E-mail")
                
                nova_senha_input = st.text_input(
                    "Nova Senha", 
                    type="password", 
                    help="Requisitos: 1 maiúscula, 1 minúscula e 1 número."
                )
                
                btn_cadastrar = st.form_submit_button("Finalizar Cadastro")

                if btn_cadastrar:
                    # 1. Preenchimento dos campos básicos
                    if not (nome_input and novo_usuario_input and email_input and email_confirm_input and nova_senha_input):
                        st.error("Por favor, preencha todos os campos do formulário.")

                    # 2. Validação da Chave Dinâmica do Professor
                    elif tipo_usuario_input == "Professor" and chave_prof_input != chave_valida_hoje:
                        st.error("Chave de verificação do Professor inválida ou expirada.")

                    # 3. Validação de e-mail
                    elif email_input != email_confirm_input:
                        st.error("Os e-mails digitados não coincidem.")
                    elif not validar_email_formato(email_input):
                        st.error("Por favor, informe um e-mail válido.")

                    # 4. Validação da força da senha
                    elif not validar_forca_senha(nova_senha_input):
                        st.error("A senha deve conter pelo menos uma letra maiúscula, uma minúscula e um número.")

                    # 5. Salvar no banco
                    else:
                        sucesso = cadastrar_usuario(
                            username=novo_usuario_input,
                            nome=nome_input,
                            email=email_input,
                            tipo=tipo_usuario_input,
                            senha_pura=nova_senha_input
                        )
                        if sucesso:
                            st.success("Conta criada com sucesso! Faça login na aba ao lado.")
                        else:
                            st.warning("Este nome de usuário já está em uso.")

            # --- DICA PARA TESTES EM AMBIENTE DE DESENVOLVIMENTO ---
                st.info(f"Chave válida hoje: **{chave_valida_hoje}**")