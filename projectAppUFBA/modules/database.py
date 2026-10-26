import sqlite3
import bcrypt

def conectar():
    return sqlite3.connect("plataforma.db")

def garantir_usuario_admin():
    conn = conectar()
    c = conn.cursor()

    # 1. Consulta se o 'admin' já existe no banco
    c.execute("SELECT username FROM usuarios WHERE username = ?", ("admin",))
    admin_existe = c.fetchone()

    # 2. Se NÃO existir, faz a criptografia e cadastra
    if not admin_existe:
        senha_pura = "Admin123!"
        senha_bytes = senha_pura.encode('utf-8')
        salt = bcrypt.gensalt(rounds=12)
        hash_str = bcrypt.hashpw(senha_bytes, salt).decode('utf-8')

        c.execute(
            "INSERT INTO usuarios (username, nome, email, tipo, password) VALUES (?, ?, ?, ?, ?)",
            ("admin", "Coordenador Geral", "admin@escola.com", "Administrador", hash_str)
        )
        conn.commit()

    conn.close()

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
        
    # --- CRIA O ADMIN PADRÃO CASO NÃO EXISTA ---
    c.execute("SELECT username FROM usuarios WHERE username = 'admin'")
    if not c.fetchone():
        senha_bytes = "Admin123!".encode('utf-8')
        salt = bcrypt.gensalt()
        hash_str = bcrypt.hashpw(senha_bytes, salt).decode('utf-8')
        
        c.execute(
            "INSERT INTO usuarios (username, nome, email, tipo, password) VALUES (?, ?, ?, ?, ?)",
            ("admin", "Coordenador Geral", "admin@escola.com", "Administrador", hash_str)
        )
    conn.commit()
    conn.close()


def verificar_login(username_digitado, senha_digitada):
    """Busca o hash no banco e valida a senha digitada no container."""
    conn = conectar()
    c = conn.cursor()

    # 1. Busca no banco de dados o registro do usuário digitado
    c.execute("SELECT nome, password FROM usuarios WHERE username = ?", (username_digitado,))
    resultado = c.fetchone()
    conn.close()

    if resultado:
        nome_usuario, hash_do_banco_str = resultado

        # 2. Prepara os dados em formato de bytes para o bcrypt
        senha_digitada_bytes = senha_digitada.encode('utf-8')
        hash_salvo_bytes = hash_do_banco_str.encode('utf-8')

        # 3. COMPARAÇÃO EXPLÍCITA OCORRE AQUI:
        # bcrypt.checkpw extrai o salt do hash salvo e verifica a senha digitada
        if bcrypt.checkpw(senha_digitada_bytes, hash_salvo_bytes):
            return nome_usuario  # Retorna o nome para salvar na sessão

    return None  # Retorna None se o usuário não existir ou a senha for inválida

def cadastrar_usuario(username, nome, email, tipo, senha_pura):
    """Gera o hash com bcrypt e cadastra o usuário com seu perfil no banco."""
    conn = conectar()
    c = conn.cursor()

    senha_bytes = senha_pura.encode('utf-8')
    salt = bcrypt.gensalt()
    hash_bytes = bcrypt.hashpw(senha_bytes, salt)
    hash_str = hash_bytes.decode('utf-8')

    try:
        c.execute(
            "INSERT INTO usuarios (username, nome, email, tipo, password) VALUES (?, ?, ?, ?, ?)",
            (username, nome, email, tipo, hash_str)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()