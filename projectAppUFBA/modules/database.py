from contextlib import contextmanager
import psycopg2
from psycopg2 import OperationalError
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool
import json
import bcrypt
import streamlit as st
import os
import logging
import threading
from streamlit.errors import StreamlitSecretNotFoundError
from dotenv import load_dotenv
from modules.senhas import (
    candidatas_de_senha,
    senha_cabe_no_bcrypt,
    senha_confere,
    validar_forca_senha,
)

# Carrega o .env ao lado da aplicação, independente do diretório de execução.
APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(APP_ROOT, ".env"))

logger = logging.getLogger(__name__)

DB_POOL_MAX_CONNECTIONS = 10
DB_CONNECT_TIMEOUT_SECONDS = 10

# Caminho de segurança (fallback) para o SQLite local
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.db")
FALLBACK_URL = f"sqlite:///{DB_PATH}"

# APP_ENV pode vir do ambiente local ou dos Secrets do Streamlit.
APP_ENV = os.environ.get("APP_ENV")
if not APP_ENV:
    try:
        APP_ENV = st.secrets.get("APP_ENV")
    except StreamlitSecretNotFoundError:
        APP_ENV = None
APP_ENV = APP_ENV.strip().lower() if isinstance(APP_ENV, str) else None

# 1. Tenta pegar a URL do .env
DATABASE_URL = os.environ.get("DATABASE_URL")

# 2. Se não achar, tenta pegar dos Secrets (útil para quando for pro Streamlit Cloud)
if not DATABASE_URL:
    try:
        DATABASE_URL = st.secrets.get("DATABASE_URL")
    except StreamlitSecretNotFoundError:
        DATABASE_URL = None

@st.cache_resource
def _pool_postgres():
    """Cria um pool compartilhado e seguro para as threads do Streamlit."""
    dsn = DATABASE_URL
    if not dsn:
        try:
            postgres_secrets = st.secrets["postgres"]
        except (KeyError, StreamlitSecretNotFoundError):
            postgres_secrets = None
        if postgres_secrets:
            dsn = postgres_secrets.get("url")

    if not dsn:
        raise RuntimeError(
            "Nenhuma credencial de banco de dados (DATABASE_URL ou "
            "[postgres].url) foi encontrada."
        )

    return ThreadedConnectionPool(
        minconn=2,
        maxconn=DB_POOL_MAX_CONNECTIONS,
        dsn=str(dsn),
        connect_timeout=DB_CONNECT_TIMEOUT_SECONDS,
    )


# --- ESQUEMA GARANTIDO UMA VEZ POR PROCESSO ---
#
# O app nunca chamava criar_tabelas(): ela so rodava manualmente pelo
# init_db.py. Por isso, tabelas novas (como compartilhamentos_cifra) nao
# existiam no banco e a consulta quebrava com UndefinedTable.
#
# Em vez de chamar criar_tabelas() a cada rerun (o que pesaria a cada clique),
# o esquema e verificado UMA unica vez por processo do servidor, na primeira
# conexao pedida. Depois disso, o custo em cada conectar() e so a leitura de
# um booleano. O lock evita que duas sessoes simultaneas rodem a criacao ao
# mesmo tempo logo apos o servidor subir.
_ESQUEMA_PRONTO = False
_ESQUEMA_LOCK = threading.Lock()


def _garantir_esquema(pool):
    global _ESQUEMA_PRONTO
    if _ESQUEMA_PRONTO:
        return
    with _ESQUEMA_LOCK:
        if _ESQUEMA_PRONTO:  # outra thread ja terminou enquanto esperavamos
            return
        conn = pool.getconn()
        try:
            _criar_tabelas(conn)
            _ESQUEMA_PRONTO = True
        except Exception:
            # Nao marca como pronto: a proxima conexao tenta de novo.
            conn.rollback()
            logger.exception("Falha ao preparar o esquema do banco.")
            raise
        finally:
            pool.putconn(conn)


@contextmanager
def conectar():
    """Empresta uma conexao do pool e sempre a devolve ao terminar."""
    pool = _pool_postgres()
    if not _ESQUEMA_PRONTO:
        _garantir_esquema(pool)
    conn = pool.getconn()
    try:
        yield conn
    except OperationalError:
        conexao_com_falha = conn
        conn = None
        pool.putconn(conexao_com_falha, close=True)
        raise
    finally:
        if conn is not None:
            pool.putconn(conn)

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
    """Execucao manual (init_db.py). Usa o mesmo caminho unico do app."""
    _garantir_esquema(_pool_postgres())


def sincronizar_schema_banco(conn):
    """Adiciona ao banco colunas ausentes da tabela de módulos.

    A lista descreve as colunas de negócio. A coluna `id` e suas restrições
    pertencem à criação da tabela e exigem uma migração própria se mudarem.
    """
    expected_columns = [
        ("slug", "TEXT"),
        ("titulo", "TEXT"),
        ("resumo", "TEXT DEFAULT ''"),
        ("icone", "TEXT DEFAULT '📘'"),
        ("nivel", "TEXT DEFAULT ''"),
        ("dificuldade", "TEXT DEFAULT ''"),
        ("duracao", "TEXT DEFAULT ''"),
        ("cor", "TEXT DEFAULT '#4F46E5'"),
        ("pdf", "TEXT DEFAULT ''"),
        ("quiz", "TEXT DEFAULT '[]'"),
        ("categoria", "TEXT DEFAULT 'Outros'"),
        ("ordem", "INTEGER DEFAULT 900"),
        ("autor", "TEXT DEFAULT ''"),
        ("ativo", "INTEGER DEFAULT 1"),
        ("data", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
    ]

    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = %s",
            ("modulos",),
        )
        existing_columns = {row[0] for row in cursor.fetchall()}

        for column_name, definition in expected_columns:
            if column_name in existing_columns:
                continue
            cursor.execute(
                sql.SQL("ALTER TABLE {} ADD COLUMN IF NOT EXISTS {} {}").format(
                    sql.Identifier("modulos"),
                    sql.Identifier(column_name),
                    sql.SQL(definition),
                )
            )


def _criar_tabelas(conn):
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            email TEXT NOT NULL,
            tipo TEXT NOT NULL,
            password TEXT NOT NULL,
            foto_perfil BYTEA,
            primeiro_acesso INTEGER DEFAULT 1
        )
    ''')

    # 2. Inspeciona as colunas existentes na tabela
    #c.execute("SELECT * FROM information_schema.columns WHERE table_name = 'usuarios'")
    # colunas_existentes = [coluna[1] for coluna in c.fetchall()]
    # #apagado por redundancia, pois o comando abaixo ja cria as colunas caso nao existam, entao não precisa inspecionar
   
    # 3. Adiciona as colunas faltantes sem apagar dados
    c.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS primeiro_acesso INTEGER DEFAULT 1")
    c.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS email TEXT DEFAULT ''")
    c.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS tipo TEXT DEFAULT 'Aluno'")
    c.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS foto_perfil BYTEA")
        
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
    except psycopg2.IntegrityError:
        pass

    # Tabela para o Mural Criptografado
    c.execute("""
        CREATE TABLE IF NOT EXISTS mural (
            id SERIAL PRIMARY KEY,
            ativo INTEGER DEFAULT 1,
            username TEXT,
            mensagem_criptografada TEXT,
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("SELECT * FROM information_schema.columns WHERE table_name = 'mural'")
    colunas_mural = [coluna[1] for coluna in c.fetchall()]
    if "username" not in colunas_mural:
        c.execute("ALTER TABLE mural ADD COLUMN IF NOT EXISTS username TEXT DEFAULT ''")
    if "ativo" not in colunas_mural:
        c.execute("ALTER TABLE mural ADD COLUMN IF NOT EXISTS ativo INTEGER DEFAULT 1")

    # Autorizacoes de compartilhamento da cifra pessoal.
    #
    # A cifra continua sendo derivada do username de cada pessoa. Esta tabela
    # guarda apenas a permissao para o destinatario ver o dicionario do
    # remetente no mural. O par remetente/destinatario e unico, entao compartilhar
    # de novo so reativa a mesma permissao em vez de criar duplicatas.
    c.execute("""
        CREATE TABLE IF NOT EXISTS compartilhamentos_cifra (
            id SERIAL PRIMARY KEY,
            remetente TEXT NOT NULL,
            destinatario TEXT NOT NULL,
            ativo INTEGER DEFAULT 1,
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (remetente, destinatario)
        )
    """)
    c.execute("ALTER TABLE compartilhamentos_cifra ADD COLUMN IF NOT EXISTS remetente TEXT DEFAULT ''")
    c.execute("ALTER TABLE compartilhamentos_cifra ADD COLUMN IF NOT EXISTS destinatario TEXT DEFAULT ''")
   
    # Tabela dos Conteudos da Coordenacao.
    # E o caminho pelo qual o Administrador (e o Professor) publicam material
    # para os alunos. Segue o mesmo padrao do mural: nada e apagado, a linha
    # so muda ativo para 0, entao o historico do que foi publicado fica.
    c.execute("""
        CREATE TABLE IF NOT EXISTS conteudos (
            id SERIAL PRIMARY KEY,
            titulo TEXT NOT NULL,
            corpo TEXT NOT NULL,
            autor TEXT,
            ativo INTEGER DEFAULT 1,
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("SELECT * FROM information_schema.columns WHERE table_name = 'conteudos'")
    colunas_conteudos = [coluna[1] for coluna in c.fetchall()]
    if "autor" not in colunas_conteudos:
        c.execute("ALTER TABLE conteudos ADD COLUMN IF NOT EXISTS autor TEXT DEFAULT ''")
    if "ativo" not in colunas_conteudos:
        c.execute("ALTER TABLE conteudos ADD COLUMN IF NOT EXISTS ativo INTEGER DEFAULT 1")

    # Colunas do exemplo de crime, que e o que o conteudo virou.
    #
    # A tabela "conteudos" era uma lista de avisos da coordenacao. Agora cada
    # linha dela e um PERGAMINHO: um exemplo de golpe, com a mensagem falsa
    # que a pessoa receberia, os sinais de alerta e o que fazer. Por isso as
    # colunas novas sao da tabela, e nao uma tabela nova: o que a coordenacao
    # publica e o que o aluno ve, sem conversao e sem passo extra.
    #
    # "chave" e o identificador fixo do exemplo pre-colocado. E ela que
    # impede a semeadura de criar o mesmo exemplo de novo a cada boot.
    # "sinais" e "protecao" sao varias linhas, mas o SQLite nao tem lista:
    # o que existe e um texto com quebras de linha.
    colunas_crime = (
        ("chave", "TEXT DEFAULT ''"),
        ("icone", "TEXT DEFAULT '📜'"),
        ("categoria", "TEXT DEFAULT ''"),
        ("exemplo", "TEXT DEFAULT ''"),
        ("sinais", "TEXT DEFAULT ''"),
        ("protecao", "TEXT DEFAULT ''"),
        ("origem", "TEXT DEFAULT 'publicado'"),
        # O conteudo em blocos: uma lista de {tipo, texto} serializada.
        # SQLite nao tem tipo lista, entao o que existe e o proprio JSON
        # dentro de uma coluna de texto. As colunas antigas (exemplo,
        # sinais, protecao) ficaram aqui porque SQLite nao tem DROP
        # COLUMN sem recriar a tabela -- elas continuam sendo lidas para
        # conteudo publicado antes desta mudanca.
        ("blocos", "TEXT DEFAULT '[]'"),
    )
    for nome_coluna, definicao in colunas_crime:
        if nome_coluna not in colunas_conteudos:
            c.execute("ALTER TABLE conteudos ADD COLUMN IF NOT EXISTS %s %s"
                      % (nome_coluna, definicao))

    # A LGPD deixou de ser pergaminho: virou o Modulo 5, uma aula teorica.
    # As linhas antigas nao sao apagadas (o texto pode ter sido editado pela
    # coordenacao), apenas inativadas, para nao aparecerem mais na pagina
    # "Exemplos de Crimes Digitais". O UPDATE e idempotente.
    c.execute(
        "UPDATE conteudos SET ativo = 0 WHERE chave = ANY(%s)",
        (
            [
                "lei-geral-protecao-dados",
                "principios-da-lgpd",
                "responsabilidade-protecao-dados",
                "importancia-lgpd-organizacoes",
            ],
        ),
    )

    # --- MODULOS CRIADOS PELA PLATAFORMA ---
    #
    # Os modulos originais continuam em dados/modulos.json. Esta tabela
    # guarda apenas os modulos novos, criados pela pagina "Gerenciar
    # Modulos". O campo "autor" e o username de quem criou, e e ele que
    # limita a edicao/exclusao: o criador mexe no proprio modulo, o
    # Administrador mexe em todos.
    #
    # O quiz fica em uma coluna de texto com JSON, do mesmo jeito que os
    # blocos dos pergaminhos. A lista de perguntas e pequena e nao tem
    # consulta por dentro dela, entao uma tabela separada so criaria
    # juncoes para nada.
    c.execute("""
        CREATE TABLE IF NOT EXISTS modulos (
            id SERIAL PRIMARY KEY,
            slug TEXT NOT NULL UNIQUE,
            titulo TEXT NOT NULL,
            resumo TEXT DEFAULT '',
            icone TEXT DEFAULT '📘',
            nivel TEXT DEFAULT '',
            dificuldade TEXT DEFAULT '',
            duracao TEXT DEFAULT '',
            cor TEXT DEFAULT '#4F46E5',
            pdf TEXT DEFAULT '',
            quiz TEXT DEFAULT '[]',
            categoria TEXT DEFAULT 'Outros',
            ordem INTEGER DEFAULT 900,
            autor TEXT NOT NULL,
            ativo INTEGER DEFAULT 1,
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    sincronizar_schema_banco(conn)

    # Tabela do progresso de cada modulo de aprendizagem.
    #
    # Uma linha por tentativa de quiz. Nao apaga a anterior: o historico fica
    # para a equipe ver a evolucao, e o que a tela mostra e a melhor nota de
    # cada modulo. Este registro e autoavaliacao do aluno -- nao e nota nem
    # avaliacao formal de professor.
    c.execute("""
        CREATE TABLE IF NOT EXISTS progresso_modulos (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL,
            modulo TEXT NOT NULL,
            acertos INTEGER NOT NULL,
            total INTEGER NOT NULL,
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("SELECT * FROM information_schema.columns WHERE table_name = 'progresso_modulos'")
    colunas_progresso = [coluna[1] for coluna in c.fetchall()]
    if "modulo" not in colunas_progresso:
        c.execute("ALTER TABLE progresso_modulos ADD COLUMN IF NOT EXISTS modulo TEXT DEFAULT ''")
    if "username" not in colunas_progresso:
        c.execute("ALTER TABLE progresso_modulos ADD COLUMN IF NOT EXISTS username TEXT DEFAULT ''")

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
            "INSERT INTO usuarios (username, nome, email, tipo, password) VALUES (%s, %s, %s, %s, %s)",
            ("admin", "Coordenador Geral", "admin@escola.com", "Administrador", hash_str)
        )

    # --- LEITURAS CONCLUIDAS ---
    #
    # Uma linha por (aluno, modulo) que o aluno terminou de ler.
    #
    # E o que libera o quiz. A leitura e registrada AQUI, e nao so na
    # sessao, por um motivo que ja apareceu na pratica: se o registro
    # fosse so na sessao, o aluno que fechar o navegador perderia a
    # liberacao e teria que ler de novo. No banco, ela sobrevive.
    c.execute("""
        CREATE TABLE IF NOT EXISTS leituras (
            username TEXT NOT NULL,
            modulo TEXT NOT NULL,
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (username, modulo)
        )
    """)
   #Criação da tabela de seguidores, que registra quem segue quem. A chave primária é composta pelos dois usernames, garantindo que não haja duplicatas.
    c.execute('''
        CREATE TABLE IF NOT EXISTS seguidores (
            seguidor_username TEXT NOT NULL,
            seguido_username TEXT NOT NULL,
            data_inicio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (seguidor_username, seguido_username)
        )
    ''')

    # Garante a restrição única para tabelas criadas anteriormente sem a chave primária
    try:
        c.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_leituras_user_modulo ON leituras (username, modulo)"
        )
    except psycopg2.IntegrityError:
        conn.rollback()  # Reverte a transação se houver erro de integridade

    # --- EXEMPLOS DE CRIMES PRÉ-COLOCADOS ---
    #
    # Vem do arquivo dados/exemplos_crime.json, que o professor edita
    # sem tocar em código. A semeadura é idempotente pela "chave": um
    # exemplo cuja chave já está na tabela não é criado de novo. É o
    # mesmo esquema do admin acima -- o que já existe não é reescrito.
    #
    # O que o professor edita depois pela página "Gerenciar Conteúdos →
    # Exemplos de Golpe" vale mais do que o que está no arquivo: por isso a
    # semeadura não sobrescreve uma linha que já existe.
    _semear_exemplos_crime(c)

    conn.commit()


def blocos_para_texto(blocos):
    """Serializa a lista de blocos para a coluna de texto do banco.

    ensure_ascii=False de proposito: sem ele o acento vira \u00e1 dentro
    da coluna, e um banco aberto no DB Browser fica ilegivel para quem
    for conferir o conteudo depois.
    """
    if not isinstance(blocos, list):
        blocos = []
    limpos = []
    for bloco in blocos:
        if not isinstance(bloco, dict):
            continue
        tipo = str(bloco.get("tipo") or "").strip().lower()
        texto = str(bloco.get("texto") or "").strip()
        if not tipo or not texto:
            continue
        limpos.append({"tipo": tipo, "texto": texto})
    return json.dumps(limpos, ensure_ascii=False)


def blocos_do_texto(texto):
    """Le a coluna "blocos" de volta como lista.

    Devolve [] em vez de levantar erro quando a coluna esta vazia ou
    corrompida: quem chama (a pagina de pergaminhos) so quer desenhar o
    que ha, e um valor estranho no banco nao pode derrubar a tela.
    """
    if not texto:
        return []
    try:
        dados = json.loads(texto)
    except (ValueError, TypeError):
        return []
    if not isinstance(dados, list):
        return []
    return [bloco for bloco in dados if isinstance(bloco, dict)]


def _semear_exemplos_crime(c):
    """Insere no banco exemplos do JSON que ainda nao existem pela chave.

    Recebe o cursor ja aberto, porque quem chama e o criar_tabelas, que
    abre e fecha a conexao uma vez so.

    O banco e a fonte da verdade para exemplos existentes: eles nao sao
    atualizados nem inativados quando o JSON muda ou deixa de listar uma chave.
    """
    # O import e aqui dentro, e nao no topo do arquivo: o modulo dos
    # exemplos nao precisa do banco, e o banco nao precisa do modulo de
    # leitura para nada alem disto. Importar aqui evita qualquer
    # dependencia circular entre os dois.
    from modules.exemplos_crime import (
        carregar_exemplos,
        linhas_para_texto,
    )

    exemplos, _ = carregar_exemplos()

    for exemplo in exemplos:
        texto_blocos = blocos_para_texto(exemplo.get("blocos"))
        texto_sinais = linhas_para_texto(exemplo["sinais"])
        texto_protecao = linhas_para_texto(exemplo["protecao"])

        c.execute("SELECT id FROM conteudos WHERE chave = %s", (exemplo["chave"],))
        if c.fetchone():
            continue

        c.execute(
            "INSERT INTO conteudos (titulo, corpo, autor, ativo, chave, icone, "
            "categoria, exemplo, sinais, protecao, origem, blocos) "
            "VALUES (%s, %s, %s, 1, %s, %s, %s, %s, %s, %s, 'pre_colocado', %s)",
            (
                exemplo["titulo"],
                exemplo["corpo"],
                "pré-colocado",
                exemplo["chave"],
                exemplo["icone"],
                exemplo["categoria"],
                exemplo["exemplo"],
                texto_sinais,
                texto_protecao,
                texto_blocos,
            ),
        )

#Funções Novas adicionadas

@st.cache_data(ttl=300, max_entries=500, show_spinner=False)
def obter_primeiro_acesso(username):
    """Le o status de primeiro acesso sem repetir a consulta a cada rerun."""
    if not username:
        return 1
    with conectar() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT primeiro_acesso FROM usuarios WHERE username = %s",
            (username,),
        )
        resultado = c.fetchone()
        conn.rollback()
    return resultado[0] if resultado else 1


def atualizar_primeiro_acesso(username):
    """Atualiza o status de primeiro acesso do aluno para 0 após o primeiro envio ao mural."""
    with conectar() as conn:
        c = conn.cursor()
        c.execute("UPDATE usuarios SET primeiro_acesso = 0 WHERE username = %s", (username,))
        conn.commit()
    obter_primeiro_acesso.clear(username)

@st.cache_data(ttl=300, max_entries=500, show_spinner=False)
def carregar_cifras_compartilhadas(destinatario):
    """Lista os usuarios que compartilharam a cifra com o destinatario."""
    with conectar() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT remetente FROM compartilhamentos_cifra "
            "WHERE destinatario = %s AND ativo = 1 AND remetente <> %s "
            "ORDER BY remetente",
            (destinatario, destinatario),
        )
        dados = tuple(linha[0] for linha in c.fetchall())
        conn.rollback()
    return dados

def salvar_compartilhamento_cifra(remetente, destinatario):
    """Autoriza o destinatario a ver o dicionario da cifra do remetente."""
    with conectar() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO compartilhamentos_cifra (remetente, destinatario, ativo) "
            "VALUES (%s, %s, 1) "
            "ON CONFLICT (remetente, destinatario) "
            "DO UPDATE SET ativo = 1, data = CURRENT_TIMESTAMP",
            (remetente, destinatario),
        )
        conn.commit()
    carregar_cifras_compartilhadas.clear(destinatario)

def salvar_mensagem_mural(username, mensagem_criptografada):
    """Salva a mensagem associada ao usuário que a enviou"""
    with conectar() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO mural (username, mensagem_criptografada, ativo) VALUES (%s, %s, 1)",
            (username, mensagem_criptografada)
        )
        conn.commit()
    carregar_mural.clear()


@st.cache_data(ttl=300, show_spinner=False)
def carregar_mural():
    """Carrega as 100 mensagens ativas mais recentes para exibição pública.

    A lista muda somente quando alguém publica ou inativa uma mensagem.
    Por isso ela fica em cache e é invalidada pelas duas escritas abaixo,
    em vez de consultar o banco a cada rerun do mural.

    O LIMIT existe porque cada mensagem vira colunas e botões na tela, e o
    st.cache_data entrega uma cópia da lista inteira a cada chamada: sem
    teto, o mural ficaria mais pesado a cada mensagem publicada.
    """
    with conectar() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT id, username, mensagem_criptografada, data FROM mural "
            "WHERE ativo = 1 ORDER BY id DESC LIMIT 100"
        )
        dados = c.fetchall()
        conn.rollback()
    return dados


def inativar_mensagem_mural(msg_id):
    """Inativa qualquer mensagem (Apenas para Professores e Admins)"""
    with conectar() as conn:
        c = conn.cursor()
        c.execute("UPDATE mural SET ativo = 0 WHERE id = %s", (msg_id,))
        conn.commit()
    carregar_mural.clear()


def salvar_conteudo(
    titulo,
    corpo,
    autor,
    icone="📜",
    categoria="",
    exemplo="",
    sinais="",
    protecao="",
    blocos=None,
):
    """Grava um exemplo de crime publicado pela coordenacao para os alunos.

    O autor e o username de quem publicou, do mesmo jeito que no mural: serve
    para a lista mostrar quem foi, sem precisar do nome completo.

    A "chave" fica vazia de proposito: ela so identifica os exemplos
    pre-colocados que vieram do arquivo dados/exemplos_crime.json. Um
    conteudo publicado na mao nao tem chave, e por isso a resemeadura
    nunca tenta recria-lo.

    "blocos" e o conteudo de verdade: a lista de {tipo, texto} que a
    pagina desenha. Os campos de texto corrido continuam sendo gravados
    porque o painel e as listas antigas ainda os leem.
    """
    with conectar() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO conteudos (titulo, corpo, autor, ativo, chave, icone, "
            "categoria, exemplo, sinais, protecao, blocos, origem) "
            "VALUES (%s, %s, %s, 1, '', %s, %s, %s, %s, %s, %s, 'publicado')",
            (
                titulo,
                corpo,
                autor,
                icone,
                categoria,
                exemplo,
                sinais,
                protecao,
                blocos_para_texto(blocos),
            ),
        )
        conn.commit()
    carregar_pergaminhos.clear()


@st.cache_data(ttl=300, show_spinner=False)
def carregar_pergaminhos(incluir_inativos=False):
    """Carrega os exemplos na ordem gravada.

    Devolve dicionarios, e nao tuplas, porque a pagina dos pergaminhos
    usa muitos campos de cada exemplo e a tupla de dez posicoes vira
    uma lista de indices dificil de ler. A ordem e por id: os
    pre-colocados vem primeiro, na ordem do arquivo, e o que a
    coordenacao publica depois entra no fim.

    Por padrao so os ativos sao devolvidos: e o que o aluno pode ver. A
    pagina de gerenciamento passa incluir_inativos=True para conseguir
    listar, editar e reativar o que foi tirado do ar.

    Esta funcao e somente leitura. A semeadura dos exemplos do arquivo
    dados/exemplos_crime.json fica em _criar_tabelas(), que e chamada na
    preparacao do banco: carregar uma pagina nao deve abrir transacao de
    escrita no banco.
    """
    sql = (
        "SELECT id, titulo, corpo, autor, data, icone, categoria, exemplo, "
        "sinais, protecao, chave, origem, blocos, ativo FROM conteudos"
    )
    if not incluir_inativos:
        sql += " WHERE ativo = 1"
    sql += " ORDER BY id ASC"

    with conectar() as conn:
        c = conn.cursor()
        c.execute(sql)
        linhas = c.fetchall()
        conn.rollback()

    chaves = (
        "id", "titulo", "corpo", "autor", "data", "icone", "categoria",
        "exemplo", "sinais", "protecao", "chave", "origem", "blocos",
        "ativo",
    )
    # "blocos" chega do banco como texto e volta como lista: quem desenha
    # a pagina nao quer saber com o que o SQLite guarda uma lista.
    prontos = []
    for linha in linhas:
        registro = dict(zip(chaves, linha))
        registro["blocos"] = blocos_do_texto(registro.get("blocos"))
        prontos.append(registro)
    return prontos


def atualizar_conteudo(
    conteudo_id,
    titulo,
    corpo,
    icone,
    categoria,
    exemplo,
    sinais,
    protecao,
    blocos=None,
):
    """Reescreve um exemplo de crime. Usado pelo Professor e pela Coordenacao.

    A "chave" e a "origem" nao sao tocadas: a chave e o que amarra o
    exemplo pre-colocado ao arquivo de origem, e mexer nela faria a
    resemeadura criar um exemplar duplicado no proximo boot.
    """
    with conectar() as conn:
        c = conn.cursor()
        c.execute(
            "UPDATE conteudos SET titulo = %s, corpo = %s, icone = %s, "
            "categoria = %s, exemplo = %s, sinais = %s, protecao = %s, "
            "blocos = %s WHERE id = %s",
            (
                titulo,
                corpo,
                icone,
                categoria,
                exemplo,
                sinais,
                protecao,
                blocos_para_texto(blocos),
                conteudo_id,
            ),
        )
        conn.commit()
    carregar_pergaminhos.clear()


def inativar_conteudo(conteudo_id):
    """Inativa um conteudo (Apenas para Professores e Admins)."""
    with conectar() as conn:
        c = conn.cursor()
        c.execute("UPDATE conteudos SET ativo = 0 WHERE id = %s", (conteudo_id,))
        conn.commit()
    carregar_pergaminhos.clear()


def reativar_conteudo(conteudo_id):
    """Devolve um exemplo inativado para a lista do aluno."""
    with conectar() as conn:
        c = conn.cursor()
        c.execute("UPDATE conteudos SET ativo = 1 WHERE id = %s", (conteudo_id,))
        conn.commit()
    carregar_pergaminhos.clear()


# ---------------------------------------------------------------------------
# Modulos criados pela plataforma
# ---------------------------------------------------------------------------
#
# Os modulos originais continuam em dados/modulos.json. A tabela "modulos"
# guarda somente os que nascem na pagina "Gerenciar Conteudos -> Modulos".
# As funcoes abaixo sao o CRUD dessa tabela.
#
# O quiz e gravado como JSON de uma lista de:
#   {"enunciado": "...", "alternativas": ["..."], "certa": 0}
# O indice "certa" aqui e ZERO-based, que e o formato que o resto do app
# usa internamente. A conversao para o formato do JSON (1-based) acontece
# so na hora de gravar um modulo que veio do arquivo.


def _quiz_do_texto(texto):
    """Le a coluna "quiz" de volta como lista, tolerando lixo no banco.

    O banco nao precisa derrubar a tela por causa de um quiz corrompido:
    a pergunta invalida e descartada e as demais continuam valendo.
    """
    if not texto:
        return []
    try:
        dados = json.loads(texto)
    except (ValueError, TypeError):
        return []
    if not isinstance(dados, list):
        return []

    prontos = []
    for questao in dados:
        if not isinstance(questao, dict):
            continue
        enunciado = str(questao.get("enunciado") or "").strip()
        alternativas = questao.get("alternativas")
        if not enunciado or not isinstance(alternativas, list) or len(alternativas) < 2:
            continue
        alternativas = [str(alternativa) for alternativa in alternativas]
        certa = questao.get("certa")
        if (
            not isinstance(certa, int)
            or isinstance(certa, bool)
            or not (0 <= certa < len(alternativas))
        ):
            certa = 0
        prontos.append({
            "enunciado": enunciado,
            "alternativas": alternativas,
            "certa": certa,
        })
    return prontos


def _quiz_para_texto(quiz):
    """Serializa a lista de perguntas para a coluna de texto."""
    return json.dumps(quiz or [], ensure_ascii=False)


@st.cache_data(ttl=300, show_spinner=False)
def listar_modulos_banco():
    """Devolve os modulos criados na plataforma, do mais antigo ao mais novo.

    O quiz volta como lista, e nao como texto: quem chama (o carregador
    dos modulos) espera o mesmo formato dos modulos do JSON.

    O catalogo e publico e o mesmo para todos os perfis, por isso ele tem
    uma unica entrada de cache -- sem o username na chave. O cache e
    invalidado por salvar_modulo, atualizar_modulo e excluir_modulo.
    """
    with conectar() as conn:
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as c:
                c.execute(
                    "SELECT id, slug, titulo, resumo, icone, nivel, dificuldade, "
                    "duracao, cor, pdf, quiz, categoria, ordem, autor, data "
                    "FROM modulos WHERE ativo = 1 ORDER BY id ASC"
                )
                linhas = c.fetchall()
            # Consulta so de leitura: encerra a transacao para a conexao
            # voltar limpa ao pool.
            conn.rollback()
        except Exception:
            # Deixa a conexao limpa para voltar ao pool: uma transacao
            # abortada contaminaria a proxima consulta que a reaproveitar.
            conn.rollback()
            raise

    prontos = []
    for linha in linhas:
        registro = dict(linha)
        registro["quiz"] = _quiz_do_texto(registro.get("quiz"))
        prontos.append(registro)
    return prontos


def salvar_modulo(
    slug,
    titulo,
    resumo,
    icone,
    nivel,
    dificuldade,
    duracao,
    cor,
    pdf,
    quiz,
    autor,
    categoria="Outros",
):
    """Cria um modulo novo. Devolve (id, None) ou (None, motivo).

    O "motivo" e uma chave curta que a tela traduz em portugues:
    "slug_duplicado" ou o texto do erro inesperado.

    A categoria e validada pelo chamador (a tela usa a lista de
    modules/modulos.py). O valor fica no banco para o catalogo saber em que
    aba o modulo aparece.
    """
    with conectar() as conn:
        c = conn.cursor()
        try:
            c.execute(
                "INSERT INTO modulos (slug, titulo, resumo, icone, nivel, "
                "dificuldade, duracao, cor, pdf, quiz, autor, categoria, ativo) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1) "
                "RETURNING id",
                (
                    slug,
                    titulo,
                    resumo,
                    icone,
                    nivel,
                    dificuldade,
                    duracao,
                    cor,
                    pdf,
                    _quiz_para_texto(quiz),
                    autor,
                    categoria,
                ),
            )
            novo_id = c.fetchone()[0]
            conn.commit()
            listar_modulos_banco.clear()
            return novo_id, None
        except psycopg2.IntegrityError:
            conn.rollback()
            return None, "slug_duplicado"
        except Exception as erro:
            conn.rollback()
            logger.exception("Falha ao criar modulo")
            return None, str(erro)


def atualizar_modulo(
    modulo_id,
    slug,
    titulo,
    resumo,
    icone,
    nivel,
    dificuldade,
    duracao,
    cor,
    pdf,
    quiz,
    solicitante,
    tipo,
    categoria="Outros",
):
    """Reescreve um modulo do banco respeitando quem criou.

    O Administrador pode editar qualquer modulo. Os demais so podem
    editar a linha cujo "autor" e o proprio username -- a condicao vai
    no WHERE, e nao so na tela, para a regra nao depender da interface.
    """
    with conectar() as conn:
        c = conn.cursor()
        parametros = (
            slug,
            titulo,
            resumo,
            icone,
            nivel,
            dificuldade,
            duracao,
            cor,
            pdf,
            _quiz_para_texto(quiz),
            categoria,
        )
        try:
            if tipo == "Administrador":
                c.execute(
                    "UPDATE modulos SET slug = %s, titulo = %s, resumo = %s, "
                    "icone = %s, nivel = %s, dificuldade = %s, duracao = %s, "
                    "cor = %s, pdf = %s, quiz = %s, categoria = %s "
                    "WHERE id = %s",
                    parametros + (modulo_id,),
                )
            else:
                c.execute(
                    "UPDATE modulos SET slug = %s, titulo = %s, resumo = %s, "
                    "icone = %s, nivel = %s, dificuldade = %s, duracao = %s, "
                    "cor = %s, pdf = %s, quiz = %s, categoria = %s "
                    "WHERE id = %s AND autor = %s",
                    parametros + (modulo_id, solicitante),
                )
            if c.rowcount <= 0:
                conn.rollback()
                return False, "sem_permissao"
            conn.commit()
            listar_modulos_banco.clear()
            return True, None
        except psycopg2.IntegrityError:
            conn.rollback()
            return False, "slug_duplicado"
        except Exception as erro:
            conn.rollback()
            logger.exception("Falha ao atualizar modulo")
            return False, str(erro)


def excluir_modulo(modulo_id, solicitante, tipo):
    """Exclui um modulo do banco. Admin pode todos; os demais so os proprios.

    Devolve (ok, motivo), como atualizar_modulo: "sem_permissao" quando a
    linha nao existe ou nao e do solicitante, ou o texto do erro inesperado.
    """
    with conectar() as conn:
        c = conn.cursor()
        try:
            if tipo == "Administrador":
                c.execute("DELETE FROM modulos WHERE id = %s", (modulo_id,))
            else:
                c.execute(
                    "DELETE FROM modulos WHERE id = %s AND autor = %s",
                    (modulo_id, solicitante),
                )
            if c.rowcount <= 0:
                conn.rollback()
                return False, "sem_permissao"
            conn.commit()
            listar_modulos_banco.clear()
            return True, None
        except Exception as erro:
            conn.rollback()
            logger.exception("Falha ao excluir modulo")
            return False, str(erro)


def registrar_leitura(username, modulo):
    """Marca que o aluno terminou de ler o material de um modulo.

    Registrar duas vezes nao faz mal: a chave primaria e (username,
    modulo), entao o INSERT repetido atualiza a data e nao duplica a
    linha. Por isso a funcao usa INSERT OR REPLACE em vez de checar
    antes.
    """
    with conectar() as conn:
        c = conn.cursor()
        c.execute(
             """
             INSERT INTO leituras (username, modulo) VALUES (%s, %s)
             ON CONFLICT (username, modulo) DO UPDATE SET data = CURRENT_TIMESTAMP
        """,
        (username, modulo)
        )
        conn.commit()
    carregar_estado_modulos.clear(username)


@st.cache_data(ttl=300, max_entries=500, show_spinner=False)
def carregar_estado_modulos(username):
    """Carrega leituras e progresso do aluno com uma consulta ao banco.

    O resultado fica em cache por pouco tempo e e invalidado quando o aluno
    registra uma leitura ou uma tentativa de quiz.
    """
    if not username:
        return {}, set()

    # A melhor tentativa de cada modulo e escolhida pelo proprio banco
    # (DISTINCT ON), em vez de trazer todas as tentativas e comparar no
    # Python. A tabela progresso_modulos guarda uma linha por tentativa e so
    # cresce; assim chega uma linha por modulo. O desempate e o mesmo de
    # antes: mais acertos e, no empate, a tentativa mais antiga (menor id).
    with conectar() as conn:
        try:
            c = conn.cursor()
            c.execute(
                "SELECT modulo, NULL::INTEGER, NULL::INTEGER, NULL::TIMESTAMP, TRUE "
                "FROM leituras WHERE username = %s "
                "UNION ALL "
                "(SELECT DISTINCT ON (modulo) modulo, acertos, total, data, FALSE "
                " FROM progresso_modulos WHERE username = %s "
                " ORDER BY modulo, acertos DESC, id ASC)",
                (username, username),
            )
            linhas = c.fetchall()
            conn.rollback()
        except Exception:
            conn.rollback()
            raise

    lidos = set()
    progresso = {}
    for modulo, acertos, total, data, eh_leitura in linhas:
        if eh_leitura:
            lidos.add(modulo)
        else:
            progresso[modulo] = {"acertos": acertos, "total": total, "data": data}
    return progresso, lidos


def salvar_progresso_modulo(username, modulo, acertos, total):
    """Registra uma tentativa de quiz de um modulo.

    Guarda uma linha por tentativa e nao apaga as anteriores: o historico
    fica para a equipe ver a evolucao do aluno. O que a tela usa e a melhor
    nota de cada modulo, calculada em carregar_estado_modulos.

    Este e um registro de autoavaliacao -- nao e nota nem avaliacao formal
    de professor.
    """
    with conectar() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO progresso_modulos (username, modulo, acertos, total) VALUES (%s, %s, %s, %s)",
            (username, modulo, acertos, total),
        )
        conn.commit()
    carregar_estado_modulos.clear(username)
    listar_progresso_recente.clear()


@st.cache_data(ttl=60, show_spinner=False)
def contar_usuarios_por_tipo():
    """Conta as contas cadastradas por perfil para o painel inicial.

    O cache curto evita uma consulta a cada tecla digitada na home; ele é
    limpo quando alguém se cadastra.
    """
    with conectar() as conn:
        c = conn.cursor()
        c.execute("SELECT tipo, COUNT(*) FROM usuarios GROUP BY tipo")
        linhas = c.fetchall()
        conn.rollback()
    return {tipo: total for tipo, total in linhas}


@st.cache_data(ttl=60, show_spinner=False)
def listar_progresso_recente(limite=6):
    """Últimas tentativas de quiz de alunos, com o nome de quem respondeu.

    Serve para a home de Professor/Administrador mostrar movimento real da
    plataforma, em vez de números soltos. A consulta filtra por tipo porque
    essa área acompanha a turma; as tentativas da própria coordenação não são
    atividade de aluno e só poluiriam a lista.
    """
    with conectar() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT p.username, u.nome, p.modulo, p.acertos, p.total, p.data "
            "FROM progresso_modulos p "
            "JOIN usuarios u ON u.username = p.username "
            "WHERE u.tipo = 'Aluno' "
            "ORDER BY p.data DESC, p.id DESC LIMIT %s",
            (limite,),
        )
        linhas = c.fetchall()
        conn.rollback()
    return linhas


# Hash de uma senha que ninguém usa, criado uma vez quando o módulo é carregado
# (custo ~0,25 s, uma vez por processo). Serve só para o login gastar o mesmo
# tempo quando o usuário NÃO existe: sem ele, a resposta vinha na hora para
# usuário inexistente e em ~0,25 s para usuário existente (o tempo do bcrypt),
# e medindo isso dava para descobrir quais nomes de usuário estão cadastrados.
# Mesmo custo (gensalt() padrão, 12) dos hashes reais, para o tempo bater.
_HASH_FICTICIO = bcrypt.hashpw(b"senha-ficticia-so-para-igualar-o-tempo", bcrypt.gensalt()).decode("utf-8")


def verificar_login(username_digitado, senha_digitada):
    """Busca o hash no banco e valida a senha digitada no container.

    Devolve (nome, tipo) quando a senha confere, ou None. Antes devolvia só o
    nome: o perfil nunca era lido do banco, então login.py nunca gravava
    tipo_usuario na sessão e todo mundo caía no menu do Aluno.
    """
    # Nenhuma versão testável da senha (só espaços, ou acima de 72 bytes mesmo
    # sem os espaços): não pode estar certa. Sai antes de ir ao banco, e nunca
    # chega ao bcrypt, que levantaria ValueError com mais de 72 bytes.
    # O limite é conferido em cada versão (candidatas_de_senha), e não na senha
    # digitada: "Abc123" com muitos espaços pode passar de 72 bytes e caber
    # depois de limpa.
    if not candidatas_de_senha(senha_digitada):
        return None

    for tentativa in range(2):
        try:
            with conectar() as conn:
                c = conn.cursor()
                c.execute(
                    "SELECT nome, tipo, password FROM usuarios WHERE username = %s",
                    (username_digitado,),
                )
                resultado = c.fetchone()
            break
        except OperationalError:
            if tentativa == 1:
                logger.exception(
                    "Falha ao consultar credenciais após reconectar ao PostgreSQL."
                )
                raise
            logger.warning(
                "Conexão PostgreSQL caiu durante o login; tentando uma conexão nova."
            )

    if resultado:
        nome_usuario, tipo_usuario, hash_do_banco_str = resultado

        # COMPARAÇÃO EXPLÍCITA OCORRE AQUI. senha_confere testa a senha como
        # foi digitada e, se ela tinha espaço, também sem os espaços (ver
        # modules/senhas.py: contas antigas podem ter espaço na senha). Em cada
        # teste, bcrypt.checkpw extrai o salt do hash salvo e compara.
        if senha_confere(senha_digitada, hash_do_banco_str):
            return nome_usuario, tipo_usuario  # Nome e perfil para a sessão
    else:
        # Usuário inexistente: faz a MESMA comparação contra o hash fictício e
        # descarta o resultado. senha_confere testa o mesmo número de versões
        # da senha que testaria com um hash real (1, ou 2 se houver espaço),
        # então o tempo fica igual ao de um usuário existente com senha errada.
        senha_confere(senha_digitada, _HASH_FICTICIO)

    return None  # Retorna None se o usuário não existir ou a senha for inválida

def cadastrar_usuario(username, nome, email, tipo, senha_pura):
    """Gera o hash com bcrypt e cadastra o usuário com seu perfil no banco.

    Devolve "ok" em caso de sucesso, ou o motivo da recusa: "usuario_duplicado"
    ou "email_duplicado". Antes devolvia só True/False, e a tela acabava dizendo
    "nome de usuário já está em uso" para qualquer violação de integridade —
    inclusive e-mail repetido, que é outra situação e merece outra mensagem.
    """
    with conectar() as conn:
        c = conn.cursor()
        try:
            # 1. Conflitos verificados antes de gravar, para dizer qual foi.
            c.execute("SELECT 1 FROM usuarios WHERE username = %s", (username,))
            if c.fetchone():
                return "usuario_duplicado"

            c.execute("SELECT 1 FROM usuarios WHERE email = %s", (email,))
            if c.fetchone():
                return "email_duplicado"

            # 2. Gravação. Última barreira: a tela já valida, mas quem chama
            #    esta função direto não passa pela tela.
            if not senha_cabe_no_bcrypt(senha_pura):
                raise ValueError("Senha acima de 72 bytes: o bcrypt não a aceita.")
            senha_bytes = senha_pura.encode('utf-8')
            salt = bcrypt.gensalt()
            hash_bytes = bcrypt.hashpw(senha_bytes, salt)
            hash_str = hash_bytes.decode('utf-8')

            c.execute(
                "INSERT INTO usuarios (username, nome, email, tipo, password) VALUES (%s, %s, %s, %s, %s)",
                (username, nome, email, tipo, hash_str)
            )
            conn.commit()
            contar_usuarios_por_tipo.clear()
            return "ok"
        except psycopg2.IntegrityError:
            # Duas submissões com o mesmo e-mail ao mesmo tempo: o índice único
            # barrou mesmo com a checagem acima. Mesma resposta da checagem.
            return "email_duplicado"

@st.cache_data(ttl=300, max_entries=500, show_spinner=False)
def obter_dados_perfil(username):
    """Consulta puramente relacional para resgatar apenas o nome e a foto de perfil do usuário."""
    if not username:
        return None
    with conectar() as conn:
        c = conn.cursor()
        # Busca estritamente as 2 colunas necessárias (sem carregar o e-mail)
        c.execute("SELECT nome, foto_perfil FROM usuarios WHERE username = %s", (username,))
        resultado = c.fetchone()
        if not resultado:
             return None
        nome, foto = resultado
        return nome, (bytes(foto) if foto is not None else None)

def atualizar_perfil(username, nova_senha, senha_atual, novo_nome): # Função para atualizar o usuário
    with conectar() as conn: # Inicia o contexto conectando-se ao PostgreSQL de forma otimizada
        c = conn.cursor() # Instancia o ponteiro de navegação no banco
       # Se o usuário preencheu campos para trocar a senha
        if nova_senha and senha_atual:
            # Segunda trava da regra da senha nova (a primeira é a tela do
            # perfil, em perfilWidget.py). Aqui é a última parada antes do
            # UPDATE: qualquer caminho que chame esta função, hoje ou no
            # futuro, não consegue gravar senha com espaço, curta ou fora do
            # limite do bcrypt. Vem antes da consulta e do bcrypt da senha
            # atual porque não depende deles e evita trabalho à toa; a regra é
            # pública, então responder antes não revela nada sobre a conta.
            if not validar_forca_senha(nova_senha):
                return "senha_nova_invalida"
            # Senha atual sem nenhuma versão testável (só espaços, ou acima de
            # 72 bytes mesmo sem os espaços) não pode estar certa.
            if not candidatas_de_senha(senha_atual):
                return "senha_atual_incorreta"
            # Puxa o hash da senha antiga salva no banco[cite: 1, 5]
            c.execute("SELECT password FROM usuarios WHERE username = %s", (username,))
            linha = c.fetchone()
            # Conta apagada no meio da sessão: antes, fetchone() devolvia None e
            # o [0] derrubava a tela com TypeError. Agora é "senha incorreta".
            if linha is None:
                return "senha_atual_incorreta"

            # MÉTODO SEGURO: confere a senha atual com o hash original, com a
            # mesma regra de espaços do login (senha_confere). Sem isso, quem
            # entra digitando "Abc 123" não conseguiria trocar a senha
            # digitando a senha atual do mesmo jeito.
            if not senha_confere(senha_atual, linha[0]):
                # Recusa a alteração se a senha antiga estiver errada
                return "senha_atual_incorreta"
            
            # Se passou, criptografa a NOVA senha[cite: 1, 5]
            salt = bcrypt.gensalt()
            novo_hash = bcrypt.hashpw(nova_senha.encode('utf-8'), salt).decode('utf-8')
            c.execute(
                "UPDATE usuarios SET nome=%s, password=%s WHERE username=%s",
                (novo_nome, novo_hash, username)
            )
        else:
            # Atualiza apenas informações gerais e foto (sem mexer na senha)
            c.execute(
                "UPDATE usuarios SET nome=%s WHERE username=%s",
                (novo_nome, username)
            )
        conn.commit() # Confirma efetivamente a gravação da transação na base de dados
        obter_dados_perfil.clear(username) # Limpa o cache de perfil para refletir as mudanças
        listar_progresso_recente.clear() # O nome exibido na home também mudou
        c.close() # Destrói o cursor liberando recursos locais do servidor

def atualizar_foto(username, foto_bytes):
    foto_db = psycopg2.Binary(foto_bytes) if foto_bytes else None
    with conectar() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE usuarios SET foto_perfil = %s WHERE username = %s",
            (foto_db, username),
        )
        conn.commit()
        obter_dados_perfil.clear(username)  # Limpa o cache para refletir a nova foto

@st.cache_data(ttl=300, max_entries=500, show_spinner=False)
def listar_seguidos(username):
    if not username:
        return ()
    with conectar() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT seguido_username FROM seguidores "
            "WHERE seguidor_username = %s ORDER BY seguido_username",
            (username,),
        )
        dados = tuple(linha[0] for linha in c.fetchall())
        conn.rollback()
    return dados


def seguir_usuario(seguidor, seguido):
    if not seguido or seguidor == seguido:
        return
    with conectar() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO seguidores (seguidor_username, seguido_username) "
            "VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (seguidor, seguido),
        )
        conn.commit()
    listar_seguidos.clear(seguidor)


def deixar_de_seguir(seguidor, seguido):
    with conectar() as conn:
        c = conn.cursor()
        c.execute(
            "DELETE FROM seguidores "
            "WHERE seguidor_username = %s AND seguido_username = %s",
            (seguidor, seguido),
        )
        conn.commit()
    listar_seguidos.clear(seguidor)


def buscar_usuarios(termo, excluir=""):
    termo = (termo or "").strip()
    if len(termo) < 2:
        return []
    termo = termo.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    padrao = f"%{termo}%"
    with conectar() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT username, nome, tipo, foto_perfil FROM usuarios "
            "WHERE (nome ILIKE %s OR username ILIKE %s) AND username <> %s "
            "ORDER BY nome LIMIT 8",
            (padrao, padrao, excluir),
        )
        dados = [
            (u, nome, tipo, bytes(foto) if foto is not None else None)
            for u, nome, tipo, foto in c.fetchall()
        ]
        conn.rollback()
    return dados