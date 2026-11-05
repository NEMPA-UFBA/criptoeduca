import html
import textwrap

import streamlit as st

from modules.database import (
    atualizar_primeiro_acesso,
    carregar_mural,
    inativar_mensagem_mural,
    salvar_mensagem_mural,
)
from modules.criptografia import cifrar, ciphertext_visivel, decifrar


def render_sessao_interativa(modo_voluntario=False):
    username_atual = st.session_state["username"]
    # --- CSS CUSTOMIZADO PARA A TEMATICA DE CRIPTOGRAFIA ---
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

        /* Estilizacao dos blocos do mural e caixas de texto */
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
            overflow-wrap: anywhere;
        }
        </style>
    """, unsafe_allow_html=True)

    if modo_voluntario:
        if st.button("⬅️ Voltar para o Menu Principal"):
            st.session_state["voltar_para_menu"] = True
            st.rerun()

    # O item do menu que abre esta pagina se chama "Mural de Criptografia",
    # e o titulo acompanha: o nome antigo ("Sessao Interativa") prometia
    # varias sessoes de conteudo, que nunca existiram. O que existe aqui e
    # o mural.
    st.title("🔐 Mural de Criptografia")

    # Explica a cifra para quem ja passou pelo primeiro acesso (ou abriu a
    # pagina de proposito). No primeiro acesso obrigatorio, a explicacao
    # completa ficaria no caminho da tarefa; ali basta o aviso do formulario.
    if modo_voluntario or st.session_state.get("primeiro_acesso") == 0:
        st.info(
            "🔐 As mensagens do mural são cifradas com **AES-128-GCM**. "
            "A chave é a frase que você digita: ela **não é armazenada** e "
            "não há recuperação. Sem a chave, ninguém — nem o aplicativo — "
            "consegue ler a mensagem."
        )

        with st.expander("🔍 Como a cifra funciona", expanded=False):
            st.markdown(textwrap.dedent("""
                1. A sua frase-chave passa por **PBKDF2-HMAC-SHA256** com
                   600.000 repetições e um *salt* aleatório de 16 bytes. O
                   resultado é a chave de 16 bytes que o AES usa.
                2. Cada mensagem recebe um **nonce** aleatório de 12 bytes.
                   Por isso, a mesma mensagem com a mesma chave gera textos
                   cifrados diferentes.
                3. O **AES-128-GCM** cifra e autentica ao mesmo tempo: se
                   alguém alterar o texto cifrado no banco, a decifração falha
                   em vez de devolver lixo.
            """))

    # A versao no key do form e o que limpa os campos depois de um envio
    # bem-sucedido. clear_on_submit=True limparia tambem quando a validacao
    # falha (mensagem ou chave vazia), e a pessoa perderia o que escreveu.
    if "mural_form_versao" not in st.session_state:
        st.session_state["mural_form_versao"] = 0
    versao_form = st.session_state["mural_form_versao"]

    with st.form(f"form_mural_interativo_{versao_form}"):
        mensagem = st.text_area("Digite sua mensagem secreta para o mural:")
        chave = st.text_input(
            "Chave secreta:",
            type="password",
            help="A chave não é armazenada. Sem ela, a mensagem é irrecuperável.",
        )
        st.caption(
            "Guarde esta chave: ela não é armazenada e não há como recuperá-la. "
            "Chaves curtas são fáceis de adivinhar; prefira uma frase longa."
        )
        btn_enviar = st.form_submit_button("Criptografar com AES-128-GCM e Enviar")

        if btn_enviar:
            if not mensagem.strip():
                st.error("Escreva alguma mensagem antes de enviar.")
            elif not chave.strip():
                st.error("Digite uma chave antes de enviar.")
            else:
                msg_cifrada = cifrar(mensagem, chave)
                # A funcao pede dois argumentos: quem mandou e o que mandou.
                salvar_mensagem_mural(username_atual, msg_cifrada)

                if st.session_state.get("primeiro_acesso") == 1:
                    atualizar_primeiro_acesso(username_atual)
                    st.session_state["primeiro_acesso"] = 0

                st.session_state["mural_form_versao"] = versao_form + 1
                st.rerun()

    st.markdown("---")
    st.subheader("📌 Mural de Mensagens Públicas Cifradas")

    tipo_usuario = st.session_state.get("tipo_usuario", "Aluno")
    eh_gestor = tipo_usuario in ["Professor", "Administrador"]

    mensagens = carregar_mural()

    if mensagens:
        for msg_id, autor_msg, msg, data in mensagens:
            col_msg, col_botoes = st.columns([4, 1])

            with col_msg:
                # A tela mostra so o ciphertext, sem o prefixo/versao/salt/
                # nonce. O envelope completo continua no banco e e ele que o
                # decifrar usa. O escape em HTML fica como defesa em
                # profundidade.
                st.markdown(f"""
                    <div class="mural-item">
                        <span style="color: #94a3b8; font-size: 0.85rem;">🕒 {data}</span><br>
                        <span style="color: #38bdf8; font-size: 1.1rem; font-weight: bold;">{html.escape(ciphertext_visivel(msg))}</span>
                    </div>
                """, unsafe_allow_html=True)

                with st.expander("🔓 Decifrar esta mensagem"):
                    chave_leitura = st.text_input(
                        "Chave usada pelo autor:",
                        type="password",
                        key=f"chave_dec_{msg_id}",
                    )
                    if st.button("Decifrar", key=f"btn_dec_{msg_id}"):
                        try:
                            texto = decifrar(msg, chave_leitura)
                        except ValueError:
                            st.error("Esta mensagem não está no formato AES-GCM.")
                        except Exception:
                            st.error("Chave incorreta ou mensagem adulterada.")
                        else:
                            st.code(texto, language=None)

            with col_botoes:
                # O proprio autor pode limpar/excluir a sua mensagem
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
