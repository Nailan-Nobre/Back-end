import secrets
import datetime
import io
import os
from typing import Tuple

import qrcode

import bd

VALID_SECONDS = int(os.environ.get("QR_VALID_SECONDS", 120))

# ---------------------------------------------------------------------------
# URL base da página de presença — vem de variável de ambiente.
# No Render, defina: FRONTEND_URL=https://seu-projeto.vercel.app
# ---------------------------------------------------------------------------
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://127.0.0.1:5500")
PRESENCA_PATH = os.environ.get("PRESENCA_PATH", "/Hackaton/frontend/presenca.html")


def gerar_novo_qrcode_sala(
    valid_seconds: int = VALID_SECONDS,
    turma_id: str | None = None,
    disciplina_id: str | None = None,
) -> Tuple[str, bytes]:
    token = secrets.token_hex(16)
    agora = datetime.datetime.now(datetime.timezone.utc)
    expiracao = agora + datetime.timedelta(seconds=valid_seconds)

    conn = bd.get_conexao()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO tokens_qrcode (token_gerado, expira_em) VALUES (%s, %s) RETURNING id",
        (token, expiracao),
    )
    novo_token = cursor.fetchone()
    if not novo_token:
        raise RuntimeError("Nao foi possivel salvar o novo token do QR Code")
    conn.commit()

    # Monta a URL apontando para o frontend no Vercel (ou localhost em dev)
    query_params = [f"token={token}"]
    if turma_id:
        query_params.append(f"turma_id={turma_id}")
    if disciplina_id:
        query_params.append(f"disciplina_id={disciplina_id}")
    url_presenca = f"{FRONTEND_URL}{PRESENCA_PATH}?{'&'.join(query_params)}"

    img = qrcode.make(url_presenca)
    bio = io.BytesIO()
    img.save(bio, format='PNG')
    bio.seek(0)
    return token, bio.read()