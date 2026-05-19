import secrets
import datetime
import io
import os
from typing import Tuple

import qrcode

import bd

VALID_SECONDS = int(os.environ.get("QR_VALID_SECONDS", 30))

# ---------------------------------------------------------------------------
# URL base da página de presença — vem de variável de ambiente.
# No Render, defina: FRONTEND_URL=https://seu-projeto.vercel.app
# ---------------------------------------------------------------------------
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://127.0.0.1:5500")
PRESENCA_PATH = os.environ.get("PRESENCA_PATH", "/presenca.html")


def gerar_novo_qrcode_sala(
    valid_seconds: int = VALID_SECONDS,
) -> Tuple[str, bytes]:
    token = secrets.token_hex(16)
    agora = datetime.datetime.now()
    expiracao = agora + datetime.timedelta(seconds=valid_seconds)

    conn = bd.get_conexao()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO tokens_qrcode (token_gerado, expira_em) VALUES (?, ?)",
        (token, expiracao.strftime('%Y-%m-%d %H:%M:%S'))
    )
    conn.commit()

    # Monta a URL apontando para o frontend no Vercel (ou localhost em dev)
    url_presenca = f"{FRONTEND_URL}{PRESENCA_PATH}?token={token}"

    img = qrcode.make(url_presenca)
    bio = io.BytesIO()
    img.save(bio, format='PNG')
    bio.seek(0)
    return token, bio.read()