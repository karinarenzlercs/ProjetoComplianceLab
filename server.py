# -*- coding: utf-8 -*-
"""
server.py — Camada de apresentação (Flask) do Diagnóstico de Maturidade LGPD.

Substitui a interface Streamlit pelo novo design "dossiê" (templates/index.html +
static/app.js), SEM tocar no backend que já está 100% funcional:

  - motor_regras.py      — motor determinístico (score + lacunas)
  - gemini_client.py     — redação das recomendações (com fallback)
  - gerador_relatorio.py — PDF (Jinja2 + WeasyPrint)

Este arquivo apenas EXPÕE esse backend por endpoints JSON consumidos pelo
front-end:

  GET  /                        -> página única (capa, GRC, identificação)
  GET  /api/setores            -> setores suportados (chave -> rótulo)
  GET  /api/questionario/<set> -> perguntas do setor (a partir dos JSONs reais)
  POST /api/diagnostico        -> roda o motor + redação + PDF; devolve o resultado
  GET  /api/relatorio/<id>     -> baixa o PDF já gerado para aquele diagnóstico

Rodar localmente:   python server.py   (http://localhost:5000)
"""

import uuid
from flask import (
    Flask, render_template, request, jsonify, send_file, abort,
)
from io import BytesIO

import motor_regras
import gemini_client

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Armazenamento em memória dos relatórios já gerados.
#
# O PDF é montado no /api/diagnostico (enquanto a tela mostra a animação de
# "compilando o dossiê") e guardado aqui por um id efêmero; o /api/relatorio/<id>
# apenas devolve esses bytes. Suficiente para uso local / processo único.
# Em deploy com múltiplos workers, troque por um store compartilhado (ex.: Redis).
# ---------------------------------------------------------------------------

RESULTADOS: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Página principal
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@app.route("/api/setores")
def api_setores():
    """Devolve os setores suportados (chave interna -> rótulo amigável)."""
    return jsonify(motor_regras.SETORES)


@app.route("/api/questionario/<setor>")
def api_questionario(setor):
    """Devolve as perguntas do setor a partir do JSON real do motor."""
    if setor not in motor_regras.SETORES:
        return jsonify({"erro": f"Setor inválido: {setor}"}), 400
    try:
        questionario = motor_regras.carregar_questionario(setor)
    except Exception as e:  # arquivo ausente/corrompido
        return jsonify({"erro": f"Falha ao carregar o questionário: {e}"}), 500

    # Expõe apenas o que o front precisa, preservando a ordem do JSON.
    perguntas = [
        {
            "id": p["id"],
            "dimensao": p.get("dimensao", ""),
            "pergunta": p["pergunta"],
            "exemplo": p.get("exemplo", ""),
            "opcoes": p["opcoes"],
        }
        for p in questionario["perguntas"]
    ]
    return jsonify({
        "setor": setor,
        "setor_nome": questionario.get("setor_nome", motor_regras.SETORES[setor]),
        "perguntas": perguntas,
    })


@app.route("/api/diagnostico", methods=["POST"])
def api_diagnostico():
    """
    Roda o fluxo completo (motor -> redação -> PDF) e devolve o resultado.

    Corpo esperado (JSON):
        {
          "setor": "ecommerce",
          "empresa": "Loja Exemplo",
          "respostas": { "Q-EC-001": "Sim, implementado", ... }
        }
    """
    dados = request.get_json(silent=True) or {}
    setor = dados.get("setor")
    empresa = (dados.get("empresa") or "").strip()
    respostas = dados.get("respostas") or {}

    if setor not in motor_regras.SETORES:
        return jsonify({"erro": "Setor inválido."}), 400
    if not empresa:
        return jsonify({"erro": "Informe o nome da empresa."}), 400
    if not isinstance(respostas, dict) or not respostas:
        return jsonify({"erro": "Nenhuma resposta recebida."}), 400

    # Camadas 1 e 2 (motor + redação) precisam funcionar — são puras/sem GTK.
    try:
        diagnostico = motor_regras.gerar_diagnostico(setor, respostas)
        redacao = gemini_client.redigir_lacunas(diagnostico["lacunas"])
    except Exception as e:
        return jsonify({"erro": f"{type(e).__name__}: {e}"}), 500

    # O PDF é OPCIONAL: se o WeasyPrint/GTK não estiver disponível nesta máquina,
    # o relatório continua aparecendo na tela; apenas o download fica indisponível.
    rid = None
    nome_pdf = None
    pdf_erro = None
    try:
        import gerador_relatorio  # import lazy: WeasyPrint pode faltar (GTK no Windows)
        pdf_bytes = gerador_relatorio.gerar_pdf(diagnostico, redacao, empresa)
        nome_pdf = gerador_relatorio.nome_arquivo_pdf(empresa, setor)
        rid = uuid.uuid4().hex
        RESULTADOS[rid] = {"pdf": pdf_bytes, "nome": nome_pdf}
    except Exception as e:
        pdf_erro = (
            "PDF indisponível nesta máquina. No Windows, o WeasyPrint requer o "
            "GTK3 Runtime instalado. (" + f"{type(e).__name__}" + ")"
        )

    # Junta a redação às lacunas para exibição opcional na tela.
    itens = redacao.get("itens", {})
    lacunas = []
    for l in diagnostico["lacunas"]:
        red = itens.get(l["id"], {})
        lacunas.append({
            "id": l["id"],
            "controle": l["controle"],
            "dimensao": l.get("dimensao", ""),
            "artigo": l["artigo"],
            "risco": l["risco"],
            "pergunta": l.get("pergunta", ""),
            "resposta": l.get("resposta", ""),
            "descricao": red.get("descricao") or l["recomendacao_base"],
            "passos": red.get("passos") or [l["recomendacao_base"]],
        })

    return jsonify({
        "id": rid,
        "pdf_disponivel": rid is not None,
        "pdf_erro": pdf_erro,
        "empresa": empresa,
        "setor": setor,
        "setor_nome": diagnostico.get("setor_nome", ""),
        "score": diagnostico["score"],
        "nivel": diagnostico["nivel"],
        "total_lacunas": diagnostico["total_lacunas"],
        "resumo_risco": diagnostico["resumo_risco"],
        "fonte_redacao": redacao.get("fonte"),
        "aviso_redacao": redacao.get("erro"),
        "lacunas": lacunas,
        "detalhe_respostas": diagnostico.get("detalhe_respostas", []),
    })


@app.route("/api/relatorio/<rid>")
def api_relatorio(rid):
    """Devolve o PDF previamente gerado para um diagnóstico."""
    registro = RESULTADOS.get(rid)
    if not registro:
        abort(404, description="Relatório não encontrado ou expirado.")
    return send_file(
        BytesIO(registro["pdf"]),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=registro["nome"],
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
