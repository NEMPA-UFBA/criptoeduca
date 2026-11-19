"""Regras de senha num lugar só.

Antes existiam duas cópias de validar_forca_senha: uma em login.py (cadastro)
e outra em perfilWidget.py (troca de senha). Quando o cadastro passou a exigir
6 caracteres, a troca de senha continuou aceitando "Ab1". Regra de segurança
duplicada diverge; por isso as duas telas importam daqui.

Também é daqui que o login e a troca de senha conferem a senha digitada
(senha_confere), para as duas telas tratarem espaços do mesmo jeito.

Este módulo não importa Streamlit nem banco: são funções puras, testáveis sem
subir o app. A única dependência é o bcrypt, que compara a senha com o hash.
"""
import re

import bcrypt

# O bcrypt só usa os primeiros 72 BYTES da senha. A versão 5.0.0 da biblioteca
# deixou de cortar em silêncio e passou a levantar ValueError, o que derrubava
# a tela com um erro vermelho. São bytes, não caracteres: "é" ocupa 2 bytes em
# UTF-8 e um emoji ocupa 4.
LIMITE_BYTES_BCRYPT = 72

TAMANHO_MINIMO = 6


def senha_cabe_no_bcrypt(senha):
    """True se a senha cabe no limite do bcrypt (72 bytes em UTF-8)."""
    return len((senha or "").encode("utf-8")) <= LIMITE_BYTES_BCRYPT


def tem_espaco(senha):
    """True se houver qualquer caractere de espaço na senha.

    isspace() pega mais que a barra de espaço: tab, quebra de linha e o espaço
    "inquebrável" que costuma vir junto quando se copia texto de site ou PDF.
    """
    return any(c.isspace() for c in (senha or ""))


def requisitos_senha(senha):
    """Estado de cada requisito, para o checklist do cadastro.

    Senha com espaço é RECUSADA, nunca corrigida: a senha é avaliada exatamente
    como foi digitada. Tirar o espaço em silêncio no cadastro faria a pessoa
    digitar "Abc 123" no login e não entrar nunca mais.
    """
    senha = senha or ""
    return {
        "maiuscula": any(c.isupper() for c in senha),
        "minuscula": any(c.islower() for c in senha),
        "numero": any(c.isdigit() for c in senha),
        "tamanho": len(senha) >= TAMANHO_MINIMO,
        "sem_espaco": not tem_espaco(senha),
        "limite": senha_cabe_no_bcrypt(senha),
    }


def validar_forca_senha(senha):
    """Todos os requisitos atendidos, inclusive sem espaço e até 72 bytes.

    Vale para senha NOVA (cadastro e troca). Não use no login: contas criadas
    antes desta regra podem ter espaço na senha e precisam continuar entrando.
    """
    return all(requisitos_senha(senha).values())


def candidatas_de_senha(senha_digitada):
    """Versões da senha digitada que o login deve testar, em ordem.

    1. A senha exatamente como foi digitada. Vem primeiro porque é o caso
       normal e porque contas criadas de 24/09 a 18/11/2026 podem ter espaço
       na senha: o cadastro daquela época aceitava espaço e gravava a senha
       como foi digitada. Tirar os espaços sempre trancaria essas pessoas para
       fora, e o app não tem "esqueci minha senha".
    2. A mesma senha sem nenhum espaço, só quando ela tinha algum. É o que faz
       os espaços "não contarem" no login das contas novas, que nunca têm
       espaço (o cadastro passou a recusar).

    Lista vazia = nenhuma versão pode estar certa, e quem chama nem precisa
    consultar o banco. Acontece em dois casos:
    - a senha só tem espaços (ou está vazia). Nenhuma conta pode ter uma senha
      assim: o cadastro sempre exigiu maiúscula, minúscula e número;
    - todas as versões passam de 72 bytes, o limite do bcrypt.
    """
    senha_digitada = senha_digitada or ""
    sem_espacos = re.sub(r"\s+", "", senha_digitada)  # \s também pega tab e NBSP
    if not sem_espacos:
        return []
    candidatas = [senha_digitada]
    if sem_espacos != senha_digitada:
        candidatas.append(sem_espacos)
    return [c for c in candidatas if senha_cabe_no_bcrypt(c)]


def senha_confere(senha_digitada, hash_salvo):
    """True se alguma versão da senha digitada confere com o hash do banco.

    Usada no login (verificar_login) e na senha atual da troca de senha
    (atualizar_perfil). NÃO serve para senha nova: senha nova passa por
    validar_forca_senha, que recusa espaço.

    Segurança: aceitar "Abc 123" na conta cuja senha é "Abc123" não facilita a
    vida de quem tenta adivinhar, porque digitar "Abc123" sempre foi possível.
    A conta continua tendo uma única senha certa; só os espaços são ignorados.

    Custo: cada versão testada é uma checagem do bcrypt (~0,23 s, de
    propósito lenta). A segunda só acontece quando a primeira falhou E a senha
    digitada tinha espaço; any() para na primeira que confere.
    """
    if not hash_salvo:
        return False
    hash_bytes = hash_salvo.encode("utf-8") if isinstance(hash_salvo, str) else hash_salvo
    return any(
        bcrypt.checkpw(candidata.encode("utf-8"), hash_bytes)
        for candidata in candidatas_de_senha(senha_digitada)
    )
