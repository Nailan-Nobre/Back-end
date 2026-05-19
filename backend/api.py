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
    agora = datetime.datetime.now()

    conn = bd.get_conexao()
    cursor = conn.cursor()

    if not aluno_id and matricula:
        cursor.execute("SELECT id FROM alunos WHERE matricula = ?", (matricula,))
        aluno = cursor.fetchone()
        if not aluno:
            return jsonify({"erro": "Matrícula não encontrada"}), 404
        aluno_id = aluno[0]

    if not aluno_id:
        return jsonify({"erro": "aluno_id ou matricula são obrigatórios"}), 400

    cursor.execute(
        "SELECT id FROM presencas WHERE aluno_id = ? AND data_aula = ?",
        (aluno_id, data_hoje),
    )
    if cursor.fetchone():
        return jsonify({"erro": "Você já registrou sua presença hoje!"}), 400

    cursor.execute(
        "SELECT expira_em, utilizado FROM tokens_qrcode WHERE token_gerado = ?",
        (token_recebido,),
    )
    resultado = cursor.fetchone()

    if not resultado:
        return jsonify({"erro": "QR Code inválido!"}), 400

    expira_em, utilizado = resultado[0], resultado[1]
    if utilizado:
        return jsonify({"erro": "Este QR Code já foi utilizado."}), 400

    if agora > datetime.datetime.strptime(expira_em, "%Y-%m-%d %H:%M:%S"):
        return jsonify(
            {"erro": "Este QR Code já expirou! Escaneie o novo código na tela."}
        ), 400

    try:
        cursor.execute(
            "INSERT INTO presencas (aluno_id, data_aula) VALUES (?, ?)",
            (aluno_id, data_hoje),
        )
        cursor.execute(
            "UPDATE tokens_qrcode SET utilizado = 1 WHERE token_gerado = ?",
            (token_recebido,),
        )
        conn.commit()
        return jsonify({"sucesso": "Presença registrada com sucesso!"}), 200
    except Exception:
        return jsonify({"erro": "Erro ao salvar no banco."}), 500


@app.route("/qr-code", methods=["GET"])
def gerar_qr_code():
    _, image_bytes = qr.gerar_novo_qrcode_sala()
    return send_file(io.BytesIO(image_bytes), mimetype="image/png")


@app.route("/qr-config", methods=["GET"])
def qr_config():
    return jsonify({"valid_seconds": qr.VALID_SECONDS})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
