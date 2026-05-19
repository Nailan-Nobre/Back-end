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
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://127.0.0.1:5500")

CORS(app, resources={r"/*": {"origins": FRONTEND_URL}})


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
        cursor.execute("SELECT id FROM alunos WHERE matricula = %s", (matricula,))
        aluno = cursor.fetchone()
        if not aluno:
            return jsonify({"erro": "Matrícula não encontrada"}), 404
        aluno_id = aluno["id"]

    if not aluno_id:
        return jsonify({"erro": "aluno_id ou matricula são obrigatórios"}), 400

    cursor.execute(
        "SELECT 1 FROM presencas WHERE aluno_id = %s AND data_aula = %s",
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

    if expira_em is not None and expira_em.tzinfo is not None:
        agora = datetime.datetime.now(tz=expira_em.tzinfo)

    if agora > expira_em:
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
    except Exception:
        conn.rollback()
        return jsonify({"erro": "Erro ao salvar no banco."}), 500


@app.route("/qr-code", methods=["GET"])
def gerar_qr_code():
    _, image_bytes = qr.gerar_novo_qrcode_sala()
    return send_file(io.BytesIO(image_bytes), mimetype="image/png")


@app.route("/qr-config", methods=["GET"])
def qr_config():
    return jsonify({"valid_seconds": qr.VALID_SECONDS})


@app.route("/presencas", methods=["GET"])
def listar_presencas():
    data_param = request.args.get("data")
    if data_param:
        try:
            data_consulta = datetime.date.fromisoformat(data_param)
        except ValueError:
            return jsonify({"erro": "data inválida. Use YYYY-MM-DD"}), 400
    else:
        data_consulta = datetime.date.today()

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
        (data_consulta,),
    )
    registros = [
        {
            "nome": row["nome"],
            "matricula": row["matricula"],
            "hora_registro": row["hora_registro"],
        }
        for row in cursor.fetchall()
    ]
    return jsonify({"data": data_consulta.isoformat(), "registros": registros})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
