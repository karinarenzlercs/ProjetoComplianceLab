# -*- coding: utf-8 -*-
"""
motor_regras.py — Motor de regras DETERMINÍSTICO do Diagnóstico LGPD.

Esta é a CAMADA 1 da arquitetura: nada aqui usa IA. O motor apenas lê as
respostas do questionário e as cruza com a base de conhecimento curada (JSON)
para: (1) calcular o score de maturidade e (2) identificar as lacunas de
conformidade. Isso garante que nenhuma recomendação ou enquadramento jurídico
seja inventado — o Gemini (Camada 2) só redige em cima do que sai daqui.
"""

import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Constantes de configuração
# ---------------------------------------------------------------------------

# Diretório raiz do projeto (relativo a ESTE arquivo) — funciona em qualquer
# sistema operacional e também no deploy do Streamlit Cloud.
RAIZ = Path(__file__).resolve().parent
DIR_BASE = RAIZ / "base_conhecimento"
DIR_QUESTIONARIOS = RAIZ / "questionarios"

# Setores suportados. A chave é o identificador interno; o valor é o rótulo
# amigável exibido na interface.
SETORES = {
    "juridico": "Escritório de Advocacia",
    "tecnologia": "Empresa de Tecnologia / SaaS",
    "ecommerce": "E-commerce",
}

# Pontuação de cada resposta. "Não se aplica" é None porque é EXCLUÍDA do
# cálculo da média (não conta como acerto nem como erro).
PONTUACAO = {
    "Sim, implementado": 100,
    "Parcialmente": 50,
    "Não": 0,
    "Não se aplica": None,
}

# Respostas que indicam uma LACUNA de conformidade (geram recomendação).
RESPOSTAS_LACUNA = ("Não", "Parcialmente")

# Ordem de prioridade dos riscos (menor número = aparece primeiro no relatório).
ORDEM_RISCO = {"alto": 0, "medio": 1, "baixo": 2}

# Faixas de maturidade (limite superior inclusivo, em %).
NIVEIS_MATURIDADE = [
    (30, "Inicial"),
    (60, "Em Desenvolvimento"),
    (85, "Intermediário"),
    (100, "Avançado"),
]


# ---------------------------------------------------------------------------
# Carregamento dos arquivos JSON
# ---------------------------------------------------------------------------

def _carregar_json(caminho: Path) -> dict:
    """Lê um arquivo JSON em UTF-8 e devolve o dicionário correspondente."""
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")
    with open(caminho, encoding="utf-8") as fp:
        return json.load(fp)


def carregar_base_conhecimento(setor: str) -> dict:
    """Carrega a base de conhecimento (controles) de um setor."""
    if setor not in SETORES:
        raise ValueError(f"Setor inválido: '{setor}'. Use um de {list(SETORES)}.")
    return _carregar_json(DIR_BASE / f"{setor}.json")


def carregar_questionario(setor: str) -> dict:
    """Carrega o questionário (perguntas) de um setor."""
    if setor not in SETORES:
        raise ValueError(f"Setor inválido: '{setor}'. Use um de {list(SETORES)}.")
    return _carregar_json(DIR_QUESTIONARIOS / f"{setor}.json")


# ---------------------------------------------------------------------------
# Cálculo do score de maturidade
# ---------------------------------------------------------------------------

def classificar_nivel(score: float) -> str:
    """Converte um score percentual (0–100) no nível de maturidade textual."""
    for limite, nome in NIVEIS_MATURIDADE:
        if score <= limite:
            return nome
    return NIVEIS_MATURIDADE[-1][1]  # fallback (não deve ocorrer)


def calcular_score(respostas: dict) -> dict:
    """
    Calcula o score de maturidade a partir das respostas.

    `respostas` é um dicionário {pergunta_id: texto_da_resposta}.

    Retorna um dicionário com o score, o nível e contadores úteis para o
    relatório. Respostas "Não se aplica" são excluídas da média.
    """
    pontos = []          # pontuações das respostas aplicáveis
    nao_aplicaveis = 0   # quantas respostas foram "Não se aplica"

    for resposta in respostas.values():
        valor = PONTUACAO.get(resposta)
        if valor is None:
            # "Não se aplica" (ou resposta desconhecida/em branco) — não pontua.
            nao_aplicaveis += 1
            continue
        pontos.append(valor)

    total_aplicaveis = len(pontos)

    if total_aplicaveis == 0:
        # Caso extremo: nenhuma pergunta aplicável (tudo "Não se aplica").
        return {
            "score": 0.0,
            "nivel": "Não avaliável",
            "total_perguntas": len(respostas),
            "total_aplicaveis": 0,
            "total_nao_aplicaveis": nao_aplicaveis,
        }

    score = sum(pontos) / total_aplicaveis  # média simples
    score = round(score, 1)

    return {
        "score": score,
        "nivel": classificar_nivel(score),
        "total_perguntas": len(respostas),
        "total_aplicaveis": total_aplicaveis,
        "total_nao_aplicaveis": nao_aplicaveis,
    }


# ---------------------------------------------------------------------------
# Identificação das lacunas
# ---------------------------------------------------------------------------

def identificar_lacunas(respostas: dict, base: dict, questionario: dict) -> list:
    """
    Cruza as respostas com a base de conhecimento e devolve a lista de lacunas.

    Uma lacuna é gerada sempre que a resposta de um controle for "Não" ou
    "Parcialmente". Cada lacuna carrega TODOS os dados validados do controle
    (controle, artigo, risco, recomendacao_base) mais o texto da pergunta e a
    resposta dada. A lista sai ordenada por risco (alto → baixo).
    """
    # Índice pergunta_id -> texto da pergunta, para enriquecer a lacuna.
    texto_pergunta = {q["id"]: q["pergunta"] for q in questionario["perguntas"]}

    lacunas = []
    for controle in base["controles"]:
        pid = controle["pergunta_id"]
        resposta = respostas.get(pid)

        # Só vira lacuna se a resposta indicar não conformidade.
        if resposta not in RESPOSTAS_LACUNA:
            continue

        lacunas.append({
            "id": controle["id"],
            "controle": controle["controle"],
            "dimensao": controle.get("dimensao", ""),
            "artigo": controle["artigo"],
            "risco": controle["risco"],
            "pergunta_id": pid,
            "pergunta": texto_pergunta.get(pid, ""),
            "resposta": resposta,
            "recomendacao_base": controle["recomendacao_base"],
        })

    # Ordena por risco (alto primeiro) e, em empate, "Não" antes de "Parcialmente".
    lacunas.sort(key=lambda l: (
        ORDEM_RISCO.get(l["risco"], 99),
        0 if l["resposta"] == "Não" else 1,
        l["id"],
    ))
    return lacunas


def resumo_por_risco(lacunas: list) -> dict:
    """Conta quantas lacunas existem em cada nível de risco (para o relatório)."""
    resumo = {"alto": 0, "medio": 0, "baixo": 0}
    for l in lacunas:
        if l["risco"] in resumo:
            resumo[l["risco"]] += 1
    return resumo


# ---------------------------------------------------------------------------
# Função orquestradora (ponto de entrada principal do motor)
# ---------------------------------------------------------------------------

def gerar_diagnostico(setor: str, respostas: dict) -> dict:
    """
    Executa o diagnóstico completo de um setor.

    Recebe o setor e as respostas {pergunta_id: resposta} e devolve um
    dicionário estruturado e pronto para alimentar a Camada 2 (Gemini) e o
    gerador de relatório. NÃO usa IA — é 100% determinístico.
    """
    base = carregar_base_conhecimento(setor)
    questionario = carregar_questionario(setor)

    score = calcular_score(respostas)
    lacunas = identificar_lacunas(respostas, base, questionario)

    return {
        "setor": setor,
        "setor_nome": base.get("setor_nome", SETORES.get(setor, setor)),
        "versao_base": base.get("versao", ""),
        "data_revisao_base": base.get("data_revisao", ""),
        "normas_referencia": base.get("normas_referencia", ""),
        "score": score["score"],
        "nivel": score["nivel"],
        "total_aplicaveis": score["total_aplicaveis"],
        "total_nao_aplicaveis": score["total_nao_aplicaveis"],
        "total_perguntas": score["total_perguntas"],
        "total_lacunas": len(lacunas),
        "resumo_risco": resumo_por_risco(lacunas),
        "lacunas": lacunas,
    }


# ---------------------------------------------------------------------------
# Autoteste — executado apenas com `python motor_regras.py`
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Simula um diagnóstico de e-commerce: respostas variadas para exercitar
    # o cálculo do score, a exclusão de "Não se aplica" e a ordenação por risco.
    print("=== AUTOTESTE DO MOTOR DE REGRAS ===\n")

    for setor_teste in SETORES:
        q = carregar_questionario(setor_teste)
        ids = [p["id"] for p in q["perguntas"]]

        # Estratégia de teste: alterna respostas de forma determinística.
        ciclo = ["Sim, implementado", "Parcialmente", "Não", "Não se aplica"]
        respostas_teste = {pid: ciclo[i % len(ciclo)] for i, pid in enumerate(ids)}

        diag = gerar_diagnostico(setor_teste, respostas_teste)
        print(f"[{setor_teste}] {diag['setor_nome']}")
        print(f"  Score: {diag['score']}% — Nível: {diag['nivel']}")
        print(f"  Aplicáveis: {diag['total_aplicaveis']} | "
              f"Não se aplica: {diag['total_nao_aplicaveis']} | "
              f"Lacunas: {diag['total_lacunas']} {diag['resumo_risco']}")
        # Mostra as 2 primeiras lacunas (devem ser de risco alto).
        for l in diag["lacunas"][:2]:
            print(f"    - [{l['risco'].upper()}] {l['id']} {l['controle']} "
                  f"(resposta: {l['resposta']})")
        print()

    print("Autoteste concluído com sucesso.")
