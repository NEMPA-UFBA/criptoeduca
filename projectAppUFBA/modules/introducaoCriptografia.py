import streamlit as st

def render_introducao_criptografia():

    # Abas para separar a parte de vídeoaulas dos exercícios
    aba_aula, aba_quiz = st.tabs(["📹 Aulas Gravadas", "🧠 Quiz Prático"])

    with aba_aula:
        st.subheader("Módulo 1: Fundamentos de Segurança e Criptografia")
        
        # Exemplo de videoaula (você pode substituir pelo link do YouTube da aula)
        st.video("")#URL AQUI
        
        st.markdown("""
            ### 📝 Anotações e Resumo da Aula:
            * **Confidencialidade**: Garantir que apenas quem tem a chave possa ler a mensagem.
            * **Cifras Clássicas**: Introdução à substituição de caracteres e cifras históricas.
            * **Aplicações Modernas**: Como a segurança digital protege transações e dados no dia a dia.
        """)
        
    with aba_quiz:
        st.subheader("🧠 Avaliação de Conhecimento")
        
        with st.form("form_quiz_criptografia"):
            resp = st.radio(
                "Qual é o principal objetivo da criptografia em sistemas de informação?",
                [
                    "Acelerar o processamento de redes de computadores",
                    "Garantir a confidencialidade, integridade e segurança dos dados",
                    "Compactar arquivos para economizar espaço em disco"
                ]
            )
            btn_quiz = st.form_submit_button("Enviar Resposta", type="primary")

            if btn_quiz:
                if resp == "Garantir a confidencialidade, integridade e segurança dos dados":
                    st.success("Resposta correta! 🎉 Parabéns pelo avanço.")
                    # Atualiza a pontuação do aluno na sessão se desejar
                    st.session_state["pontuacao"] = st.session_state.get("pontuacao", 0) + 10
                else:
                    st.error("Incorreto. Reveja o conteúdo da videoaula e tente novamente!")