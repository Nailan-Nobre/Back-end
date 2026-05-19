import os
import sqlite3
from typing import Optional

# ---------------------------------------------------------------------------
# Caminho do banco lido de variável de ambiente.
# No Render, defina: DB_PATH=/opt/render/project/src/controle_presenca.db
# Localmente, o padrão 'controle_presenca.db' já funciona.
# ---------------------------------------------------------------------------
DB_PATH = os.environ.get("DB_PATH", "controle_presenca.db")

# Conexão global reutilizada por toda a aplicação
_conexao: Optional[sqlite3.Connection] = None


def inicializar_banco() -> sqlite3.Connection:
    global _conexao
    _conexao = sqlite3.connect(DB_PATH, check_same_thread=False)
    _conexao.row_factory = sqlite3.Row

    # Performance e integridade
    _conexao.execute("PRAGMA foreign_keys = ON;")
    _conexao.execute("PRAGMA journal_mode = WAL;")
    _conexao.execute("PRAGMA synchronous = NORMAL;")
    _conexao.execute("PRAGMA cache_size = -32000;")  # ~32 MB de cache

    cursor = _conexao.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alunos (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            nome         TEXT NOT NULL,
            matricula    TEXT UNIQUE NOT NULL,
            senha_hash   TEXT NOT NULL
        );
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tokens_qrcode (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            token_gerado TEXT UNIQUE NOT NULL,
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
            expira_em    DATETIME NOT NULL,
            utilizado    INTEGER DEFAULT 0
        );
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS presencas (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            aluno_id       INTEGER,
            data_aula      DATE NOT NULL,
            hora_registro  DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(aluno_id) REFERENCES alunos(id),
            UNIQUE(aluno_id, data_aula)
        );
    ''')

    # Índices para performance nas consultas mais comuns
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_presencas_aluno ON presencas(aluno_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tokens_token ON tokens_qrcode(token_gerado);")

    _conexao.commit()
    return _conexao


def get_conexao() -> sqlite3.Connection:
    """Retorna a conexão ativa. Garante que o banco foi inicializado."""
    if _conexao is None:
        return inicializar_banco()
    return _conexao


def inserir_dados_teste():
    """Popula o banco com alunos de exemplo. Seguro chamar várias vezes."""
    conn = get_conexao()
    cursor = conn.cursor()
    alunos_teste = [
        ('Ana Souza',       '20260001', 'senha123'),
        ('Carlos Eduardo',  '20260002', 'senha456'),
        ('Mariana Costa',   '20260003', 'senha789'),
    ]
    try:
        cursor.executemany(
            "INSERT INTO alunos (nome, matricula, senha_hash) VALUES (?, ?, ?)",
            alunos_teste
        )
        conn.commit()
        print("Alunos de teste inseridos com sucesso!")
    except sqlite3.IntegrityError:
        print("Alunos de teste já cadastrados.")


if __name__ == "__main__":
    inicializar_banco()
    inserir_dados_teste()
    print("Banco pronto.")