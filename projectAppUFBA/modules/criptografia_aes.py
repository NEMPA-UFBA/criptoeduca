"""Laboratorio de criptografia AES-128-GCM.

Laboratorio embutido na pagina do modulo especial "Laboratorio AES-128-GCM",
liberado depois da leitura e do quiz. Diferente do Mural de Criptografia,
aqui nada e gravado no banco: a mensagem existe apenas na sessao do
navegador. O objetivo e experimentar a cifra de alto nivel
(PBKDF2-HMAC-SHA256 + AES-128-GCM) sem publicar nada no mural.
"""

import streamlit as st

from modules.criptografia import cifrar, decifrar


# A unica coisa guardada na sessao e o texto cifrado: ele precisa existir
# entre um clique e outro para poder ser decifrado depois. Mensagens de erro
# e de sucesso sao desenhadas direto, na mesma execucao do envio do
# formulario, e por isso nao precisam de chave no session_state.
_CHAVE_TEXTO_CIFRADO = "aes_lab_texto_cifrado"


def _explicacao():
    with st.expander("🔍 Como o AES-128-GCM funciona", expanded=False):
        st.markdown(
            """
            1. A sua frase-chave passa por **PBKDF2-HMAC-SHA256** com
               600.000 repetições e um *salt* aleatório de 16 bytes. O
               resultado é a chave de 16 bytes que o AES usa.
            2. Cada mensagem recebe um **nonce** aleatório de 12 bytes.
               Por isso, a mesma mensagem com a mesma chave gera textos
               cifrados diferentes.
            3. O **AES-128-GCM** cifra e autentica ao mesmo tempo: se
               alguém alterar o texto cifrado, a decifração falha em vez
               de devolver lixo.
            """
        )


@st.fragment
def render_laboratorio_aes():
    """Desenha o laboratorio, sem gravar nada no banco.

    E um fragmento: cifrar e decifrar redesenham so o laboratorio, e nao a
    pagina inteira. Os dois formularios validam na mesma execucao do envio,
    sem callback, entao os avisos aparecem direto, sem guardar nada na sessao.
    O texto decifrado aparece so logo depois do envio e nao fica guardado:
    o texto aberto nao permanece na memoria do servidor.
    """
    st.info(
        "🧪 **Laboratório de criptografia de alto nível.** Aqui você pode "
        "cifrar e decifrar mensagens com **AES-128-GCM**. Nada é publicado "
        "no mural: o texto fica só nesta sessão do navegador."
    )
    _explicacao()

    st.subheader("🔒 Criptografar")
    with st.form("aes_lab_form_cifrar"):
        mensagem = st.text_area(
            "Texto:",
            placeholder="Escreva o texto que você quer cifrar...",
        )
        chave = st.text_input(
            "Chave:",
            type="password",
            help="A chave não é armazenada. Sem ela, a mensagem é irrecuperável.",
        )
        cifrar_agora = st.form_submit_button("Criptografar", type="primary")

    if cifrar_agora:
        if not mensagem.strip():
            st.error("Escreva alguma mensagem antes de cifrar.")
        elif not chave.strip():
            st.error("Digite uma frase-chave antes de cifrar.")
        else:
            st.session_state[_CHAVE_TEXTO_CIFRADO] = cifrar(mensagem, chave)
            st.success("Mensagem cifrada.")

    texto_cifrado = st.session_state.get(_CHAVE_TEXTO_CIFRADO)
    if not texto_cifrado:
        return

    st.markdown("**Texto cifrado:**")
    st.code(texto_cifrado, language=None)
    st.caption(
        "Para conferir, digite a mesma chave abaixo. O texto cifrado fica "
        "guardado apenas nesta sessão."
    )

    st.divider()
    st.subheader("🔓 Decifrar")
    # clear_on_submit: a chave digitada nao fica no campo depois do envio.
    with st.form("aes_lab_form_decifrar", clear_on_submit=True):
        chave_dec = st.text_input("Chave para decifrar:", type="password")
        decifrar_agora = st.form_submit_button("Decifrar", type="primary")

    if decifrar_agora:
        if not chave_dec.strip():
            st.error("Digite a frase-chave antes de decifrar.")
            return
        try:
            texto = decifrar(texto_cifrado, chave_dec)
        except ValueError:
            st.error("Este texto não está no formato AES-GCM.")
        except Exception:
            st.error("Chave incorreta ou mensagem adulterada.")
        else:
            st.success("Mensagem decifrada:")
            st.code(texto, language=None)
