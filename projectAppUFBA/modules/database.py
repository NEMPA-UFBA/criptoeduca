import sqlite3
import bcrypt
import streamlit as st

def conectar():
    return sqlite3.connect("plataforma.db")


def _senha_admin_inicial():
    """Le a senha do Administrador de st.secrets. Sem valor padrao no codigo.

    Esta funcao so e chamada quando o banco ainda nao tem o usuario admin, ou
    seja, uma unica vez, no primeiro boot. A senha nao e lida em nenhum outro
    momento: depois disso o que fica no banco e o hash bcrypt, e e ele que
    autentica todo mundo.

    Levanta erro em vez de devolver um valor padrao. Um default aqui
    significaria um admin com senha conhecida no codigo-fonte, que e
    exatamente o que a migracao para st.secrets veio remover.
    """
    try:
        return st.secrets["ADMIN_SENHA"]
    except Exception as erro:
        raise RuntimeError(
            "Falta ADMIN_SENHA no gerenciador de segredos. O banco ainda nao tem "
            "o usuario 'admin', entao a senha inicial e obrigatoria. Crie "
            ".streamlit/secrets.toml com ADMIN_SENHA = \"...\" (esse caminho ja "
            "esta no .gitignore) e rode de novo. Detalhe: %s" % erro
        ) from erro


def criar_tabelas():
    conn = conectar()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            email TEXT NOT NULL,
            tipo TEXT NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    # 2. Inspeciona as colunas existentes na tabela
    c.execute("PRAGMA table_info(usuarios)")
    colunas_existentes = [coluna[1] for coluna in c.fetchall()]

    # 3. Adiciona as colunas faltantes sem apagar dados
    if "email" not in colunas_existentes:
        c.execute("ALTER TABLE usuarios ADD COLUMN email TEXT DEFAULT ''")

    if "tipo" not in colunas_existentes:
        c.execute("ALTER TABLE usuarios ADD COLUMN tipo TEXT DEFAULT 'Aluno'")
        
    # --- E-MAIL ÚNICO ---
    # Índice único em vez de UNIQUE na definição da tabela: o SQLite não tem
    # ALTER TABLE ... ADD CONSTRAINT, mas CREATE UNIQUE INDEX aplica a mesma
    # restrição sobre a tabela que já existe, sem recriá-la nem tocar nos dados.
    # O CREATE TABLE IF NOT EXISTS acima é inerte para banco já criado, então
    # esta é a única forma de a restrição valer para quem já tem o banco.
    # É defesa em profundidade: o formulário já checa duplicidade antes de
    # inserir. Se algum dado antigo impedir o índice, o app segue funcionando
    # pela checagem do formulário, em vez de quebrar na inicialização.
    try:
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_usuarios_email ON usuarios (email)")
    except sqlite3.IntegrityError:
        pass

    # --- ADMIN PADRÃO, SÓ SE O BANCO AINDA NÃO TIVER UM ---
    # A senha não está no código: vem de st.secrets, e só é lida neste ramo.
    # Como o banco do repositório já tem o admin, esta linha não executa, e a
    # ausência do secrets.toml não quebra o app em uso normal.
    c.execute("SELECT username FROM usuarios WHERE username = 'admin'")
    if not c.fetchone():
        senha_bytes = _senha_admin_inicial().encode('utf-8')
        salt = bcrypt.gensalt()
        hash_str = bcrypt.hashpw(senha_bytes, salt).decode('utf-8')

        c.execute(
            "INSERT INTO usuarios (username, nome, email, tipo, password) VALUES (?, ?, ?, ?, ?)",
            ("admin", "Coordenador Geral", "admin@escola.com", "Administrador", hash_str)
        )
    conn.commit()
    conn.close()


def verificar_login(username_digitado, senha_digitada):
    """Busca o hash no banco e valida a senha digitada no container.

    Devolve (nome, tipo) quando a senha confere, ou None. Antes devolvia só o
    nome: o perfil nunca era lido do banco, então login.py nunca gravava
    tipo_usuario na sessão e todo mundo caía no menu do Aluno.
    """
    conn = conectar()
    c = conn.cursor()

    # 1. Busca no banco de dados o registro do usuário digitado
    c.execute("SELECT nome, tipo, password FROM usuarios WHERE username = ?", (username_digitado,))
    resultado = c.fetchone()
    conn.close()

    if resultado:
        nome_usuario, tipo_usuario, hash_do_banco_str = resultado

        # 2. Prepara os dados em formato de bytes para o bcrypt
        senha_digitada_bytes = senha_digitada.encode('utf-8')
        hash_salvo_bytes = hash_do_banco_str.encode('utf-8')

        # 3. COMPARAÇÃO EXPLÍCITA OCORRE AQUI:
        # bcrypt.checkpw extrai o salt do hash salvo e verifica a senha digitada
        if bcrypt.checkpw(senha_digitada_bytes, hash_salvo_bytes):
            return nome_usuario, tipo_usuario  # Nome e perfil para a sessão

    return None  # Retorna None se o usuário não existir ou a senha for inválida

def cadastrar_usuario(username, nome, email, tipo, senha_pura):
    """Gera o hash com bcrypt e cadastra o usuário com seu perfil no banco.

    Devolve "ok" em caso de sucesso, ou o motivo da recusa: "usuario_duplicado"
    ou "email_duplicado". Antes devolvia só True/False, e a tela acabava dizendo
    "nome de usuário já está em uso" para qualquer violação de integridade —
    inclusive e-mail repetido, que é outra situação e merece outra mensagem.
    """
    conn = conectar()
    c = conn.cursor()

    try:
        # 1. Conflitos verificados antes de gravar, para dizer qual foi.
        c.execute("SELECT 1 FROM usuarios WHERE username = ?", (username,))
        if c.fetchone():
            return "usuario_duplicado"

        c.execute("SELECT 1 FROM usuarios WHERE email = ?", (email,))
        if c.fetchone():
            return "email_duplicado"

        # 2. Gravação
        senha_bytes = senha_pura.encode('utf-8')
        salt = bcrypt.gensalt()
        hash_bytes = bcrypt.hashpw(senha_bytes, salt)
        hash_str = hash_bytes.decode('utf-8')

        c.execute(
            "INSERT INTO usuarios (username, nome, email, tipo, password) VALUES (?, ?, ?, ?, ?)",
            (username, nome, email, tipo, hash_str)
        )
        conn.commit()
        return "ok"
    except sqlite3.IntegrityError:
        # Duas submissões com o mesmo e-mail ao mesmo tempo: o índice único
        # barrou mesmo com a checagem acima. Mesma resposta da checagem.
        return "email_duplicado"
    finally:
        conn.close()