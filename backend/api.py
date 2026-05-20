import datetime
import io
import os

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

import bd
import qr

app = Flask(__name__)

# ---------------------------------------------------------------------------
# CORS — lê a origem permitida de variável de ambiente.
# No Render, defina: FRONTEND_URL=https://seu-projeto.vercel.app
# Localmente, crie um .env ou exporte: export FRONTEND_URL=http://127.0.0.1:5500
# ---------------------------------------------------------------------------
FRONTEND_URL = os.environ.get("FRONTEND_URL", "")
ALLOWED_ORIGINS = {
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    FRONTEND_URL,
}
ALLOWED_ORIGINS = [origin for origin in ALLOWED_ORIGINS if origin]

CORS(app, resources={r"/*": {"origins": ALLOWED_ORIGINS}})


# ---------------------------------------------------------------------------
# Inicializa o banco ao subir a aplicação
# ---------------------------------------------------------------------------
bd.inicializar_banco()


def _obter_turma_id(cursor) -> int:
    turma_id_env = os.environ.get("TURMA_ID")
    if turma_id_env:
        return int(turma_id_env)

    cursor.execute("SELECT id FROM turmas ORDER BY id LIMIT 1")
    turma = cursor.fetchone()
    if turma:
        return turma["id"]

    codigo = f"GERAL-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    cursor.execute(
        "INSERT INTO turmas (nome, codigo, descricao) VALUES (%s, %s, %s) RETURNING id",
        ("Turma Geral", codigo, "Criada automaticamente"),
    )
    return cursor.fetchone()["id"]


@app.route("/presenca", methods=["POST", "OPTIONS"])
def registrar_presenca():
    payload = request.get_json(silent=True) or {}
    form_data = request.form or {}

    aluno_id = payload.get("aluno_id") or form_data.get("aluno_id")
    matricula = payload.get("matricula") or form_data.get("matricula")
    token_recebido = payload.get("token") or form_data.get("token")

    if not token_recebido:
        return jsonify({"erro": "token é obrigatório"}), 400

    data_hoje = datetime.date.today()
    agora = datetime.datetime.now(datetime.timezone.utc)

    conn = bd.get_conexao()
    cursor = conn.cursor()

    if not aluno_id and matricula:
        cursor.execute("SELECT id FROM alunos WHERE matricula = %s", (matricula,))
        aluno = cursor.fetchone()
        if not aluno:
            return jsonify({"erro": "Matrícula não encontrada"}), 404
        aluno_id = aluno["id"]

    if not aluno_id:
        return jsonify({"erro": "aluno_id ou matricula são obrigatórios"}), 400

    cursor.execute(
        "SELECT id FROM presencas WHERE aluno_id = %s AND data_aula = %s",
        (aluno_id, data_hoje),
    )
    if cursor.fetchone():
        return jsonify({"erro": "Você já registrou sua presença hoje!"}), 400

    cursor.execute(
        "SELECT expira_em, utilizado FROM tokens_qrcode WHERE token_gerado = %s",
        (token_recebido,),
    )
    resultado = cursor.fetchone()

    if not resultado:
        return jsonify({"erro": "QR Code inválido!"}), 400

    expira_em = resultado["expira_em"]
    utilizado = resultado["utilizado"]
    if utilizado:
        return jsonify({"erro": "Este QR Code já foi utilizado."}), 400

    if isinstance(expira_em, str):
        expira_em_dt = datetime.datetime.fromisoformat(expira_em)
    else:
        expira_em_dt = expira_em

    if expira_em_dt.tzinfo is None:
        expira_em_dt = expira_em_dt.replace(tzinfo=datetime.timezone.utc)

    if agora > expira_em_dt:
        return jsonify(
            {"erro": "Este QR Code já expirou! Escaneie o novo código na tela."}
        ), 400

    try:
        cursor.execute(
            "INSERT INTO presencas (aluno_id, data_aula) VALUES (%s, %s)",
            (aluno_id, data_hoje),
        )
        cursor.execute(
            "UPDATE tokens_qrcode SET utilizado = TRUE WHERE token_gerado = %s",
            (token_recebido,),
        )
        conn.commit()
        return jsonify({"sucesso": "Presença registrada com sucesso!"}), 200
    except Exception as exc:
        conn.rollback()
        app.logger.exception("Erro ao salvar no banco")
        return jsonify({"erro": "Erro ao salvar no banco.", "detalhe": str(exc)}), 500


@app.route("/presencas", methods=["GET"])
def listar_presencas():
    data_hoje = datetime.date.today()
    conn = bd.get_conexao()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT a.nome, a.matricula, p.hora_registro
        FROM presencas p
        JOIN alunos a ON a.id = p.aluno_id
        WHERE p.data_aula = %s
        ORDER BY p.hora_registro DESC
        """,
        (data_hoje,),
    )
    registros = cursor.fetchall() or []
    return jsonify({"registros": registros}), 200


@app.route("/encerrar-chamada", methods=["POST"])
def encerrar_chamada():
    payload = request.get_json(silent=True) or {}
    data_hoje = datetime.date.today()
    titulo = payload.get("titulo") or f"Chamada {data_hoje.isoformat()}"

    conn = bd.get_conexao()
    cursor = conn.cursor()
    try:
        turma_id = _obter_turma_id(cursor)
        cursor.execute(
            "INSERT INTO listas_presenca (turma_id, data_aula, titulo) VALUES (%s, %s, %s) RETURNING id",
            (turma_id, data_hoje, titulo),
        )
        lista_id = cursor.fetchone()["id"]
        cursor.execute(
            "UPDATE presencas SET lista_id = %s WHERE data_aula = %s AND lista_id IS NULL",
            (lista_id, data_hoje),
        )
        conn.commit()
        return jsonify({"lista_id": lista_id, "titulo": titulo}), 200
    except Exception as exc:
        conn.rollback()
        app.logger.exception("Erro ao encerrar chamada")
        return jsonify({"erro": "Erro ao encerrar chamada.", "detalhe": str(exc)}), 500


@app.route("/turmas", methods=["GET"])
def listar_turmas():
    conn = bd.get_conexao()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, nome, codigo, descricao, criado_em, cor FROM turmas ORDER BY criado_em DESC"
    )
    turmas = cursor.fetchall() or []
    return jsonify({"turmas": turmas}), 200


@app.route("/turmas", methods=["POST"])
def criar_turma():
    payload = request.get_json(silent=True) or {}
    nome = (payload.get("nome") or "").strip()
    codigo = (payload.get("codigo") or "").strip()
    descricao = (payload.get("descricao") or "").strip() or None
    cor = (payload.get("cor") or "").strip() or None

    if not nome or not codigo:
        return jsonify({"erro": "nome e codigo sao obrigatorios"}), 400

    conn = bd.get_conexao()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO turmas (nome, codigo, descricao, cor) VALUES (%s, %s, %s, %s) RETURNING id",
            (nome, codigo, descricao, cor),
        )
        turma_id = cursor.fetchone()["id"]
        conn.commit()
        return jsonify({"id": turma_id}), 201
    except Exception as exc:
        conn.rollback()
        app.logger.exception("Erro ao criar turma")
        return jsonify({"erro": "Erro ao criar turma.", "detalhe": str(exc)}), 500


@app.route("/qr-code", methods=["GET"])
def gerar_qr_code():
    _, image_bytes = qr.gerar_novo_qrcode_sala()
    return send_file(io.BytesIO(image_bytes), mimetype="image/png")


@app.route("/qr-config", methods=["GET"])
def qr_config():
    return jsonify({"valid_seconds": qr.VALID_SECONDS})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
