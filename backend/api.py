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
ALLOWED_ORIGINS = [
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    FRONTEND_URL,
]
ALLOWED_ORIGINS = [origin for origin in ALLOWED_ORIGINS if origin]

CORS(app, resources={r"/*": {"origins": ALLOWED_ORIGINS}})


@app.after_request
def aplicar_cors_em_respostas(response):
    origin = request.headers.get("Origin")
    if origin and origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Access-Control-Allow-Methods"] = (
            "GET, POST, PUT, DELETE, OPTIONS"
        )
    return response


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
    # Para requisições OPTIONS (preflight CORS)
    if request.method == "OPTIONS":
        return jsonify({}), 200

    payload = request.get_json(silent=True) or {}

    # Extrair dados do payload
    nome = payload.get("nome", "").strip()
    matricula = payload.get("matricula", "").strip()
    token_recebido = payload.get("token")
    turma_id = payload.get("turma_id")
    disciplina_id = payload.get("disciplina_id")

    # Validações básicas
    if not token_recebido:
        return jsonify({"erro": "Token é obrigatório"}), 400

    if not nome or not matricula:
        return jsonify({"erro": "Nome e matrícula são obrigatórios"}), 400

    data_hoje = datetime.date.today()
    agora = datetime.datetime.now(datetime.timezone.utc)

    conn = bd.get_conexao()
    cursor = conn.cursor()

    def _to_int_or_none(v):
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return None
        try:
            return int(v)
        except Exception:
            return None

    turma_id_int = _to_int_or_none(turma_id)
    disciplina_id_int = _to_int_or_none(disciplina_id)

    try:
        # 1. Buscar o aluno pela matrícula
        cursor.execute(
            "SELECT id, nome FROM alunos WHERE TRIM(matricula) = %s", (matricula,)
        )
        aluno = cursor.fetchone()

        if not aluno:
            app.logger.warning(f"Aluno não encontrado com matrícula: {matricula}")
            return jsonify(
                {
                    "erro": f"Matrícula '{matricula}' não encontrada. Verifique se você está cadastrado."
                }
            ), 404

        aluno_id = aluno["id"]
        aluno_nome = aluno["nome"]

        # 2. Verificar se o nome informado corresponde ao nome cadastrado (opcional, mas recomendado)
        if nome.lower() != aluno_nome.lower():
            app.logger.warning(
                f"Nome não corresponde: enviado='{nome}', cadastrado='{aluno_nome}'"
            )
            return jsonify(
                {
                    "erro": f"Nome informado não corresponde ao cadastrado para esta matrícula."
                }
            ), 400

        # 3. Verificar token do QR Code
        cursor.execute(
            "SELECT expira_em, utilizado FROM tokens_qrcode WHERE token_gerado = %s",
            (token_recebido,),
        )
        resultado = cursor.fetchone()

        if not resultado:
            return jsonify(
                {"erro": "QR Code inválido! Escaneie o QR Code da tela do professor."}
            ), 400

        expira_em = resultado["expira_em"]
        utilizado = resultado["utilizado"]

        if utilizado:
            return jsonify(
                {"erro": "Este QR Code já foi utilizado. Escaneie um novo QR Code."}
            ), 400

        # Converter expira_em para datetime se for string
        if isinstance(expira_em, str):
            expira_em_dt = datetime.datetime.fromisoformat(expira_em)
        else:
            expira_em_dt = expira_em

        if expira_em_dt.tzinfo is None:
            expira_em_dt = expira_em_dt.replace(tzinfo=datetime.timezone.utc)

        if agora > expira_em_dt:
            return jsonify(
                {"erro": "Este QR Code expirou! Peça ao professor para gerar um novo."}
            ), 400

        # 4. Se turma_id não foi fornecido, tentar buscar do token ou usar padrão
        if turma_id_int is None:
            # Buscar a turma do aluno (primeira turma associada)
            cursor.execute(
                """
                SELECT turma_id FROM alunos_turmas 
                WHERE aluno_id = %s 
                LIMIT 1
            """,
                (aluno_id,),
            )
            turma_assoc = cursor.fetchone()
            if turma_assoc:
                turma_id_int = turma_assoc["turma_id"]
            else:
                turma_id_int = _obter_turma_id(cursor)

        # 5. Verificar se o aluno já registrou presença hoje
        cursor.execute(
            """
            SELECT id FROM presencas
            WHERE aluno_id = %s
              AND data_aula = %s
              AND turma_id IS NOT DISTINCT FROM %s
              AND disciplina_id IS NOT DISTINCT FROM %s
            """,
            (aluno_id, data_hoje, turma_id_int, disciplina_id_int),
        )
        if cursor.fetchone():
            return jsonify(
                {"erro": "Você já registrou sua presença nesta chamada hoje!"}
            ), 400

        # 6. Registrar presença
        cursor.execute(
            """
            INSERT INTO presencas (aluno_id, turma_id, disciplina_id, data_aula, hora_registro)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (aluno_id, turma_id_int, disciplina_id_int, data_hoje, agora),
        )

        # 7. Marcar token como utilizado
        cursor.execute(
            "UPDATE tokens_qrcode SET utilizado = TRUE WHERE token_gerado = %s",
            (token_recebido,),
        )

        conn.commit()

        app.logger.info(
            f"Presença registrada: Aluno {aluno_nome} ({matricula}) - Turma {turma_id_int}"
        )

        return jsonify(
            {"sucesso": f"Presença registrada com sucesso! Bem-vindo(a), {aluno_nome}."}
        ), 200

    except Exception as exc:
        conn.rollback()
        app.logger.exception("Erro ao registrar presença")
        return jsonify(
            {"erro": "Erro interno ao registrar presença.", "detalhe": str(exc)}
        ), 500


@app.route("/presencas", methods=["GET"])
def listar_presencas():
    data_hoje = datetime.date.today()
    turma_id = request.args.get("turma_id")
    disciplina_id = request.args.get("disciplina_id")
    conn = bd.get_conexao()
    cursor = conn.cursor()
    try:
        filtros = ["p.data_aula = %s", "p.lista_id IS NULL"]
        params = [data_hoje]
        if turma_id:
            filtros.append("p.turma_id = %s")
            params.append(turma_id)
        if disciplina_id:
            filtros.append("p.disciplina_id = %s")
            params.append(disciplina_id)

        cursor.execute(
            """
            SELECT a.nome, a.matricula, p.hora_registro, p.turma_id, p.disciplina_id
            FROM presencas p
            JOIN alunos a ON a.id = p.aluno_id
            WHERE """
            + " AND ".join(filtros)
            + """
            ORDER BY p.hora_registro DESC
            """,
            params,
        )
        registros = cursor.fetchall() or []
        return jsonify({"registros": registros}), 200
    except Exception as exc:
        app.logger.exception("Erro ao listar presencas")
        return (
            jsonify({"erro": "Erro ao listar presencas.", "detalhe": str(exc)}),
            500,
        )


@app.route("/encerrar-chamada", methods=["POST"])
def encerrar_chamada():
    payload = request.get_json(silent=True) or {}
    data_hoje = datetime.date.today()
    titulo = payload.get("titulo") or f"Chamada {data_hoje.isoformat()}"
    disciplina_id_raw = payload.get("disciplina_id")
    turma_id_payload = payload.get("turma_id")
    try:
        disciplina_id = (
            None
            if disciplina_id_raw is None
            or (isinstance(disciplina_id_raw, str) and disciplina_id_raw.strip() == "")
            else int(disciplina_id_raw)
        )
    except Exception:
        disciplina_id = None

    conn = bd.get_conexao()
    cursor = conn.cursor()
    try:
        turma_id = (
            int(turma_id_payload) if turma_id_payload else _obter_turma_id(cursor)
        )
        cursor.execute(
            """
            INSERT INTO listas_presenca (turma_id, data_aula, titulo, disciplina_id)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (turma_id, disciplina_id, data_aula)
            DO UPDATE SET titulo = EXCLUDED.titulo
            RETURNING id
            """,
            (turma_id, data_hoje, titulo, disciplina_id),
        )
        lista_id = cursor.fetchone()["id"]
        cursor.execute(
            """
            UPDATE presencas
            SET lista_id = %s
            WHERE data_aula = %s
                            AND turma_id IS NOT DISTINCT FROM %s
                            AND disciplina_id IS NOT DISTINCT FROM %s
              AND lista_id IS NULL
            """,
            (lista_id, data_hoje, turma_id, disciplina_id),
        )
        conn.commit()

        # Após encerrar, gerar novo token QR para próxima chamada
        try:
            novo_token, _png = qr.gerar_novo_qrcode_sala(
                turma_id=turma_id, disciplina_id=disciplina_id
            )
        except Exception:
            novo_token = None

        return jsonify(
            {"lista_id": lista_id, "titulo": titulo, "novo_token": novo_token}
        ), 200
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


@app.route("/turmas/<int:turma_id>", methods=["GET"])
def obter_turma(turma_id: int):
    conn = bd.get_conexao()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, nome, codigo, descricao, criado_em, cor FROM turmas WHERE id = %s",
        (turma_id,),
    )
    turma = cursor.fetchone()
    if not turma:
        return jsonify({"erro": "Turma nao encontrada"}), 404
    return jsonify(turma), 200


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


@app.route("/listas", methods=["GET"])
def listar_listas_presenca():
    turma_id = request.args.get("turma_id")
    disciplina_id = request.args.get("disciplina_id")

    conn = bd.get_conexao()
    cursor = conn.cursor()

    filtros = []
    params = []
    if turma_id:
        filtros.append("lp.turma_id = %s")
        params.append(turma_id)
    if disciplina_id:
        filtros.append("lp.disciplina_id = %s")
        params.append(disciplina_id)

    where_clause = f"WHERE {' AND '.join(filtros)}" if filtros else ""
    cursor.execute(
        f"""
        SELECT
            lp.id,
            lp.turma_id,
            lp.disciplina_id,
            d.nome AS disciplina_nome,
            lp.data_aula,
            lp.titulo,
            lp.criado_em,
            COUNT(p.id) AS total_presencas
        FROM listas_presenca lp
        LEFT JOIN disciplinas d ON d.id = lp.disciplina_id
        LEFT JOIN presencas p ON p.lista_id = lp.id
        {where_clause}
        GROUP BY lp.id, lp.turma_id, lp.disciplina_id, d.nome, lp.data_aula, lp.titulo, lp.criado_em
        ORDER BY lp.data_aula DESC, lp.criado_em DESC
        """,
        params,
    )
    listas = cursor.fetchall() or []
    return jsonify({"listas": listas}), 200


@app.route("/listas/<int:lista_id>/presencas", methods=["GET"])
def listar_presencas_da_lista(lista_id: int):
    conn = bd.get_conexao()
    cursor = conn.cursor()
    try:
        # Obter turma_id da lista
        cursor.execute(
            "SELECT turma_id, disciplina_id FROM listas_presenca WHERE id = %s",
            (lista_id,),
        )
        lista = dict(cursor.fetchone() or {})
        if not lista:
            return jsonify({"erro": "Lista não encontrada"}), 404

        turma_id = lista["turma_id"]

        # Retorna todos os alunos vinculados à turma e marca presença quando houver registro na lista
        cursor.execute(
            """
            SELECT a.nome, a.matricula, p.hora_registro, (p.id IS NOT NULL) AS presente
            FROM alunos a
            JOIN alunos_turmas at ON at.aluno_id = a.id
            LEFT JOIN presencas p ON p.aluno_id = a.id AND p.lista_id = %s
            WHERE at.turma_id = %s
            ORDER BY a.nome ASC
            """,
            (lista_id, turma_id),
        )
        registros = [dict(registro) for registro in (cursor.fetchall() or [])]
        # Garantir que o campo 'presente' seja booleano no JSON
        for r in registros:
            r["presente"] = bool(r.get("presente"))
        return jsonify({"registros": registros}), 200
    except Exception as exc:
        app.logger.exception("Erro ao listar presencas da lista")
        return jsonify(
            {"erro": "Erro ao listar presencas da lista.", "detalhe": str(exc)}
        ), 500


@app.route("/alunos", methods=["GET"])
def listar_alunos():
    turma_id = request.args.get("turma_id")

    conn = bd.get_conexao()
    cursor = conn.cursor()

    if turma_id:
        cursor.execute(
            """
            SELECT a.id, a.nome, a.matricula
            FROM alunos a
            JOIN alunos_turmas at ON at.aluno_id = a.id
            WHERE at.turma_id = %s
            ORDER BY a.nome ASC
            """,
            (turma_id,),
        )
    else:
        cursor.execute("SELECT id, nome, matricula FROM alunos ORDER BY nome ASC")

    alunos = cursor.fetchall() or []
    return jsonify({"alunos": alunos}), 200


@app.route("/alunos", methods=["POST"])
def criar_aluno():
    payload = request.get_json(silent=True) or {}
    nome = (payload.get("nome") or "").strip()
    matricula = (payload.get("matricula") or "").strip()
    turma_id = payload.get("turma_id")

    if not nome or not matricula or not turma_id:
        return jsonify({"erro": "nome, matricula e turma_id sao obrigatorios"}), 400

    conn = bd.get_conexao()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id FROM alunos WHERE matricula = %s", (matricula,))
        aluno = cursor.fetchone()
        if aluno:
            aluno_id = aluno["id"]
        else:
            cursor.execute(
                "INSERT INTO alunos (nome, matricula) VALUES (%s, %s) RETURNING id",
                (nome, matricula),
            )
            aluno_id = cursor.fetchone()["id"]

        cursor.execute(
            "INSERT INTO alunos_turmas (aluno_id, turma_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (aluno_id, turma_id),
        )
        conn.commit()
        return jsonify({"id": aluno_id}), 201
    except Exception as exc:
        conn.rollback()
        app.logger.exception("Erro ao criar aluno")
        return jsonify({"erro": "Erro ao criar aluno.", "detalhe": str(exc)}), 500


@app.route("/alunos/lote", methods=["POST"])
def criar_alunos_lote():
    payload = request.get_json(silent=True) or {}
    turma_id = payload.get("turma_id")
    alunos = payload.get("alunos") or []

    if not turma_id or not isinstance(alunos, list) or not alunos:
        return jsonify({"erro": "turma_id e alunos sao obrigatorios"}), 400

    conn = bd.get_conexao()
    cursor = conn.cursor()

    criados = 0
    vinculados = 0
    ignorados = 0

    try:
        for item in alunos:
            nome = (item.get("nome") or "").strip()
            matricula = (item.get("matricula") or "").strip()

            if not nome or not matricula:
                ignorados += 1
                continue

            cursor.execute(
                """
                INSERT INTO alunos (nome, matricula)
                VALUES (%s, %s)
                ON CONFLICT (matricula)
                DO UPDATE SET nome = EXCLUDED.nome
                RETURNING id
                """,
                (nome, matricula),
            )
            aluno_id = cursor.fetchone()["id"]
            criados += 1

            cursor.execute(
                "INSERT INTO alunos_turmas (aluno_id, turma_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (aluno_id, turma_id),
            )
            vinculados += 1

        conn.commit()
        return (
            jsonify(
                {
                    "criados": criados,
                    "vinculados": vinculados,
                    "ignorados": ignorados,
                }
            ),
            201,
        )
    except Exception as exc:
        conn.rollback()
        app.logger.exception("Erro ao criar alunos em lote")
        return (
            jsonify({"erro": "Erro ao criar alunos em lote.", "detalhe": str(exc)}),
            500,
        )


@app.route("/disciplinas/<int:turma_id>", methods=["GET"])
def listar_disciplinas(turma_id: int):
    conn = bd.get_conexao()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, nome, criado_em FROM disciplinas WHERE turma_id = %s ORDER BY criado_em DESC",
        (turma_id,),
    )
    disciplinas = cursor.fetchall() or []
    return jsonify(disciplinas), 200


@app.route("/disciplinas", methods=["POST"])
def criar_disciplina():
    payload = request.get_json(silent=True) or {}
    nome = (payload.get("nome") or "").strip()
    turma_id = payload.get("turma_id")

    if not nome or not turma_id:
        return jsonify({"erro": "nome e turma_id sao obrigatorios"}), 400

    conn = bd.get_conexao()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO disciplinas (turma_id, nome) VALUES (%s, %s) RETURNING id",
            (turma_id, nome),
        )
        disciplina_id = cursor.fetchone()["id"]
        conn.commit()
        return jsonify({"id": disciplina_id}), 201
    except Exception as exc:
        conn.rollback()
        app.logger.exception("Erro ao criar disciplina")
        return jsonify({"erro": "Erro ao criar disciplina.", "detalhe": str(exc)}), 500


@app.route("/qr-code", methods=["GET"])
def gerar_qr_code():
    turma_id = request.args.get("turma_id")
    disciplina_id = request.args.get("disciplina_id")
    _, image_bytes = qr.gerar_novo_qrcode_sala(
        turma_id=turma_id,
        disciplina_id=disciplina_id,
    )
    return send_file(io.BytesIO(image_bytes), mimetype="image/png")


@app.route("/qr-config", methods=["GET"])
def qr_config():
    return jsonify({"valid_seconds": qr.VALID_SECONDS})


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
