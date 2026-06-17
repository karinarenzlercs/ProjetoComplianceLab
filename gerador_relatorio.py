# -*- coding: utf-8 -*-
"""
gerador_relatorio.py — Geração do relatório PDF (Jinja2 + WeasyPrint).

Este módulo é a "costura" final: recebe o diagnóstico determinístico
(motor_regras) e a redação (gemini_client), mescla os dois, monta o contexto
do template e devolve o PDF em BYTES — pronto para o botão de download do
Streamlit, sem precisar gravar arquivo em disco.

Importante sobre o Windows: o WeasyPrint depende das DLLs do GTK3. Quando o app
é iniciado pelo Streamlit, o GTK já está no PATH do sistema, então o import
abaixo funciona normalmente.
"""

from pathlib import Path
from datetime import datetime

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

# ---------------------------------------------------------------------------
# Configuração de caminhos (relativos a ESTE arquivo — deploy-safe)
# ---------------------------------------------------------------------------

RAIZ = Path(__file__).resolve().parent
DIR_TEMPLATES = RAIZ / "templates"
NOME_TEMPLATE = "relatorio.html"

# Mapeia o nível de maturidade para a classe CSS que colore a barra do score.
# Baixo desempenho = vermelho; intermediário = âmbar; bom = verde.
CLASSE_BARRA_POR_NIVEL = {
    "Inicial": "nivel-baixo",
    "Em Desenvolvimento": "nivel-medio",
    "Intermediário": "nivel-bom",
    "Avançado": "nivel-bom",
    "Não avaliável": "",  # mantém o azul padrão do CSS
}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _formatar_data_iso(data_iso: str) -> str:
    """Converte 'AAAA-MM-DD' para 'DD/MM/AAAA'. Se falhar, devolve o original."""
    try:
        return datetime.strptime(data_iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return data_iso or ""


def _mesclar_lacunas(diagnostico: dict, redacao: dict) -> list:
    """
    Junta cada lacuna (dados jurídicos do motor) com sua redação (Gemini).

    Se, por qualquer motivo, faltar a redação de uma lacuna, usa a
    recomendacao_base como descrição e um passo único — o relatório nunca
    fica com campos vazios.
    """
    itens = redacao.get("itens", {}) if redacao else {}
    lacunas_render = []

    for l in diagnostico["lacunas"]:
        red = itens.get(l["id"], {})
        descricao = red.get("descricao") or l["recomendacao_base"]
        passos = red.get("passos") or [l["recomendacao_base"]]

        lacunas_render.append({
            "id": l["id"],
            "controle": l["controle"],
            "dimensao": l.get("dimensao", ""),
            "artigo": l["artigo"],
            "risco": l["risco"],
            "descricao": descricao,
            "passos": passos,
        })
    return lacunas_render


def montar_contexto(diagnostico: dict, redacao: dict, empresa: str,
                    data_geracao: str = None) -> dict:
    """
    Monta o dicionário de contexto exatamente no formato que o template espera.
    """
    # Data do diagnóstico: usa a informada ou a data atual, em PT-BR.
    if not data_geracao:
        data_geracao = datetime.now().strftime("%d/%m/%Y")

    return {
        "empresa": empresa or "Não informada",
        "setor_nome": diagnostico.get("setor_nome", ""),
        "data_geracao": data_geracao,
        "normas_referencia": diagnostico.get("normas_referencia", "LGPD (Lei nº 13.709/2018)"),
        "score": diagnostico.get("score", 0),
        "nivel": diagnostico.get("nivel", ""),
        "classe_barra": CLASSE_BARRA_POR_NIVEL.get(diagnostico.get("nivel", ""), ""),
        "total_aplicaveis": diagnostico.get("total_aplicaveis", 0),
        "total_nao_aplicaveis": diagnostico.get("total_nao_aplicaveis", 0),
        "total_lacunas": diagnostico.get("total_lacunas", 0),
        "resumo_risco": diagnostico.get("resumo_risco", {"alto": 0, "medio": 0, "baixo": 0}),
        "versao_base": diagnostico.get("versao_base", ""),
        "data_revisao_base": _formatar_data_iso(diagnostico.get("data_revisao_base", "")),
        "lacunas": _mesclar_lacunas(diagnostico, redacao),
    }


# ---------------------------------------------------------------------------
# Função pública principal
# ---------------------------------------------------------------------------

def gerar_pdf(diagnostico: dict, redacao: dict, empresa: str,
              data_geracao: str = None) -> bytes:
    """
    Gera o relatório PDF e o devolve em BYTES.

    Parâmetros:
      diagnostico: saída de motor_regras.gerar_diagnostico().
      redacao:     saída de gemini_client.redigir_lacunas().
      empresa:     nome da empresa (aparece no cabeçalho; não vai ao Gemini).
      data_geracao: data opcional (DD/MM/AAAA); se omitida, usa a data atual.

    Retorna os bytes do PDF, prontos para st.download_button.
    """
    contexto = montar_contexto(diagnostico, redacao, empresa, data_geracao)

    # Carrega o template com autoescape ligado: protege o HTML caso a redação
    # do Gemini contenha caracteres especiais (<, >, &).
    env = Environment(
        loader=FileSystemLoader(str(DIR_TEMPLATES)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template(NOME_TEMPLATE)
    html_renderizado = template.render(**contexto)

    # base_url permite que o WeasyPrint resolva caminhos relativos (imagens etc.).
    pdf_bytes = HTML(string=html_renderizado, base_url=str(RAIZ)).write_pdf()
    return pdf_bytes


def nome_arquivo_pdf(empresa: str, setor: str) -> str:
    """Sugere um nome de arquivo seguro para o download do PDF."""
    base = (empresa or "empresa").strip().lower()
    # Mantém apenas letras, números e hífen/sublinhado para um nome de arquivo válido.
    base = "".join(c if c.isalnum() else "_" for c in base).strip("_") or "empresa"
    data = datetime.now().strftime("%Y%m%d")
    return f"diagnostico_lgpd_{base}_{data}.pdf"


# ---------------------------------------------------------------------------
# Autoteste — fluxo completo (motor -> gemini -> PDF) com `python gerador_relatorio.py`
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import motor_regras
    import gemini_client

    print("=== AUTOTESTE DO GERADOR DE RELATÓRIO (fluxo completo) ===\n")

    setor = "ecommerce"
    q = motor_regras.carregar_questionario(setor)
    ids = [p["id"] for p in q["perguntas"]]

    # Respostas simuladas: gera algumas lacunas de risco variado.
    ciclo = ["Sim, implementado", "Parcialmente", "Não", "Não se aplica"]
    respostas = {pid: ciclo[i % len(ciclo)] for i, pid in enumerate(ids)}

    # 1) Camada 1 — motor de regras (determinístico).
    diag = motor_regras.gerar_diagnostico(setor, respostas)
    print(f"Diagnóstico: score={diag['score']}% nível={diag['nivel']} "
          f"lacunas={diag['total_lacunas']}")

    # 2) Camada 2 — redação (Gemini ou fallback).
    redacao = gemini_client.redigir_lacunas(diag["lacunas"])
    print(f"Redação: fonte={redacao['fonte']}")

    # 3) Geração do PDF.
    pdf = gerar_pdf(diag, redacao, empresa="Loja Exemplo Ltda.")
    nome = nome_arquivo_pdf("Loja Exemplo Ltda.", setor)
    with open(nome, "wb") as fp:
        fp.write(pdf)
    print(f"PDF gerado: {nome} ({round(len(pdf)/1024, 1)} KB)")
    print("\nAutoteste concluído.")
