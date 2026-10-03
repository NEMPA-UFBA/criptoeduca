import streamlit as st

def render_introducao_criptografia():

    # Abas para separar a parte de vídeoaulas dos exercícios
    aba_aula, aba_quiz = st.tabs(["📹 Aulas Gravadas", "🧠 Quiz Prático"])

    with aba_aula:
        st.subheader("Módulo 1: Fundamentos de Segurança e Criptografia")
        
        # A URL da videoaula entra aqui quando o conteudo estiver pronto.
        #
        # Ela nao pode ser passada vazia para o st.video: ele trata o argumento
        # como caminho de arquivo, tenta abrir "" e levanta
        # MediaFileStorageError. Como o st.tabs roda as duas abas na mesma
        # passada, essa excecao nao derrubava so a aba da aula -- derrubava a
        # pagina inteira, incluindo o quiz e o titulo. O if mantem o campo
        # seguro para quem preencher a URL depois.
        url_aula = ""
        if url_aula.strip():
            st.video(url_aula)
        else:
            st.info("Videoaula ainda não disponível.")
        
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
                else:
                    st.error("Incorreto. Reveja o conteúdo da videoaula e tente novamente!")