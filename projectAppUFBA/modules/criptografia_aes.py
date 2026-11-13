"""Laboratorio de criptografia AES-128-GCM.

Laboratorio embutido na pagina do modulo especial "Laboratorio AES-128-GCM",
liberado depois da leitura e do quiz. Diferente do Mural de Criptografia,
aqui nada e gravado no banco: a mensagem existe apenas na sessao do
navegador. O objetivo e experimentar a cifra de alto nivel
(PBKDF2-HMAC-SHA256 + AES-128-GCM) sem publicar nada no mural.
"""

import streamlit as st

from modules.criptografia import cifrar, decifrar


_CHAVE_ERRO_CIFRAR = "_aes_erro_cifrar"
_CHAVE_AVISO_CIFRAR = "_aes_aviso_cifrar"
_CHAVE_ERRO_DECIFRAR = "_aes_erro_decifrar"
_CHAVE_TEXTO_DECIFRADO = "_aes_texto_decifrado"


def _cifrar_mensagem():
    """Cifra a mensagem como callback do botao.

    Os widgets existem na tela quando o callback roda, entao os valores sao
    lidos do session_state. O texto cifrado fica guardado apenas na sessao e
    sera usado pelo campo de decifrar no rerun seguinte.
    """
    mensagem = st.session_state.get("aes_lab_mensagem", "")
    chave = st.session_state.get("aes_lab_chave", "")

    if not mensagem.strip():
        st.session_state[_CHAVE_ERRO_CIFRAR] = (
            "Escreva alguma mensagem antes de cifrar."
        )
        return
    if not chave.strip():
        st.session_state[_CHAVE_ERRO_CIFRAR] = (
            "Digite uma frase-chave antes de cifrar."
        )
        return

    st.session_state[_CHAVE_ERRO_CIFRAR] = None
    st.session_state["aes_lab_texto_cifrado"] = cifrar(mensagem, chave)
    st.session_state.pop("aes_lab_chave_dec", None)
    st.session_state.pop(_CHAVE_ERRO_DECIFRAR, None)
    st.session_state[_CHAVE_TEXTO_DECIFRADO] = None
    st.session_state[_CHAVE_AVISO_CIFRAR] = (
        "Mensagem cifrada."
    )


def _decifrar_mensagem():
    """Decifra o texto gerado nesta sessao como callback do botao."""
    texto_cifrado = st.session_state.get("aes_lab_texto_cifrado", "")
    chave_dec = st.session_state.get("aes_lab_chave_dec", "")

    st.session_state[_CHAVE_TEXTO_DECIFRADO] = None
    if not texto_cifrado:
        st.session_state[_CHAVE_ERRO_DECIFRAR] = (
            "Cifre uma mensagem antes de decifrar."
        )
        return
    if not chave_dec.strip():
        st.session_state[_CHAVE_ERRO_DECIFRAR] = (
            "Digite a frase-chave antes de decifrar."
        )
        return

    try:
        texto = decifrar(texto_cifrado, chave_dec)
    except ValueError:
        st.session_state[_CHAVE_ERRO_DECIFRAR] = (
            "Este texto não está no formato AES-GCM."
        )
        return
    except Exception:
        st.session_state[_CHAVE_ERRO_DECIFRAR] = (
            "Chave incorreta ou mensagem adulterada."
        )
        return

    st.session_state[_CHAVE_ERRO_DECIFRAR] = None
    st.session_state[_CHAVE_TEXTO_DECIFRADO] = texto


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


def render_laboratorio_aes():
    """Desenha o laboratorio, sem gravar nada no banco."""
    st.info(
        "🧪 **Laboratório de criptografia de alto nível.** Aqui você pode "
        "cifrar e decifrar mensagens com **AES-128-GCM**. Nada é publicado "
        "no mural: o texto fica só nesta sessão do navegador."
    )
    _explicacao()

    st.subheader("🔒 Criptografar")
    st.text_area(
        "Texto:",
        key="aes_lab_mensagem",
        placeholder="Escreva o texto que você quer cifrar...",
    )
    st.text_input(
        "Chave:",
        type="password",
        key="aes_lab_chave",
        help="A chave não é armazenada. Sem ela, a mensagem é irrecuperável.",
    )

    st.button(
        "Criptografar",
        key="aes_lab_btn_cifrar",
        type="primary",
        on_click=_cifrar_mensagem,
    )
    erro = st.session_state.pop(_CHAVE_ERRO_CIFRAR, None)
    if erro:
        st.error(erro)
    aviso = st.session_state.pop(_CHAVE_AVISO_CIFRAR, None)
    if aviso:
        st.success(aviso)

    texto_cifrado = st.session_state.get("aes_lab_texto_cifrado")
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
    st.text_input(
        "Chave para decifrar:",
        type="password",
        key="aes_lab_chave_dec",
    )

    st.button(
        "Decifrar",
        key="aes_lab_btn_decifrar",
        type="primary",
        on_click=_decifrar_mensagem,
    )
    erro = st.session_state.pop(_CHAVE_ERRO_DECIFRAR, None)
    if erro:
        st.error(erro)
    texto = st.session_state.get(_CHAVE_TEXTO_DECIFRADO)
    if texto is not None:
        st.success("Mensagem decifrada:")
        st.code(texto, language=None)
