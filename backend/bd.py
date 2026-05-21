import os
from typing import Any, Optional, cast

from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row

load_dotenv()

# ---------------------------------------------------------------------------
# Conexao Postgres (Supabase) lida de variavel de ambiente.
# Use DATABASE_URL ou SUPABASE_DB_URL no .env/Render.
# ---------------------------------------------------------------------------
DB_URL = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
if not DB_URL:
    raise RuntimeError("DATABASE_URL ou SUPABASE_DB_URL nao configurado")

# Conexao global reutilizada por toda a aplicacao
_conexao: Optional[psycopg.Connection] = None


def inicializar_banco() -> psycopg.Connection:
    global _conexao
    db_url = DB_URL
    if not db_url:
        raise RuntimeError("DATABASE_URL ou SUPABASE_DB_URL nao configurado")
    _conexao = psycopg.connect(
        db_url,
        row_factory=cast(Any, dict_row),
        connect_timeout=5,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=3,
    )
    return _conexao


def get_conexao() -> psycopg.Connection:
    """Retorna a conexão ativa. Garante que o banco foi inicializado."""
    if _conexao is None or _conexao.closed:
        return inicializar_banco()

    try:
        with _conexao.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except (psycopg.OperationalError, psycopg.InterfaceError, psycopg.DatabaseError):
        try:
            _conexao.rollback()
        except Exception:
            pass
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
            "INSERT INTO alunos (nome, matricula, senha_hash) VALUES (%s, %s, %s)",
            alunos_teste
        )
        conn.commit()
        print("Alunos de teste inseridos com sucesso!")
    except psycopg.errors.UniqueViolation:
        conn.rollback()
        print("Alunos de teste já cadastrados.")


if __name__ == "__main__":
    inicializar_banco()
    inserir_dados_teste()
    print("Banco pronto.")