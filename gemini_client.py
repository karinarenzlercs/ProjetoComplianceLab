# -*- coding: utf-8 -*-
"""
gemini_client.py — Integração com o Google Gemini Flash (CAMADA 2: só redação).

REGRA DE OURO DA ARQUITETURA: o Gemini NÃO decide nada de jurídico. Ele recebe
as lacunas JÁ identificadas e validadas pelo motor de regras (Camada 1) e apenas
as redige bem: uma descrição clara do risco e um passo a passo acionável.

Princípios implementados aqui:
  - PRIVACIDADE: nada que identifique a empresa é enviado ao Gemini. Só vão os
    dados técnicos do controle (id, controle, artigo, risco, recomendação base).
  - RESILIÊNCIA: erro 429 (rate limit) é tratado com retry e backoff exponencial.
  - À PROVA DE FALHA: se a API ficar indisponível, um fallback determinístico
    (baseado na própria base de conhecimento) garante que o relatório nunca quebre.
"""

import os
import re
import json
import time
from pathlib import Path

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

# Carrega variáveis do .env usando CAMINHO EXPLÍCITO (ao lado deste arquivo).
# Isso evita o comportamento do load_dotenv() de procurar o .env a partir do
# diretório de quem chamou — garantindo que a chave seja encontrada sempre,
# inclusive quando o app é iniciado de outro diretório.
load_dotenv(Path(__file__).resolve().parent / ".env")

# Nome do modelo (configurável pelo .env). Gemini Flash é gratuito e rápido.
# Obs.: "gemini-2.0-flash" pode estar com quota zerada em algumas chaves;
# "gemini-2.5-flash" é o padrão estável e disponível.
MODELO_PADRAO = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Parâmetros de retry/backoff para o erro 429 e indisponibilidades temporárias.
MAX_TENTATIVAS = 4          # número máximo de tentativas por chamada
BACKOFF_BASE_SEG = 2.0      # atraso base; cresce 2^tentativa (2s, 4s, 8s...)

# Prompt base (instrução de sistema). Reforça: só redigir, retornar JSON puro.
PROMPT_SISTEMA = (
    "Você é um especialista em LGPD e proteção de dados. Com base nas lacunas "
    "de conformidade identificadas abaixo, redija para cada uma: (1) uma "
    "descrição clara do risco em linguagem profissional e acessível, e (2) um "
    "passo a passo detalhado e acionável para implementação. Escreva em português "
    "do Brasil. NÃO invente artigos, prazos ou obrigações: baseie-se apenas na "
    "recomendação fornecida. Retorne APENAS JSON válido, sem texto adicional e "
    "sem blocos de código markdown. Estrutura esperada: "
    '[{"id": "EC-001", "descricao": "...", "passos": ["...", "..."]}]. '
    "Lacunas:\n"
)


# ---------------------------------------------------------------------------
# Utilidades internas
# ---------------------------------------------------------------------------

def api_disponivel() -> bool:
    """Indica se há uma chave de API configurada (sem expor seu valor)."""
    chave = os.getenv("GEMINI_API_KEY", "").strip()
    return bool(chave)


def _anonimizar_lacunas(lacunas: list) -> list:
    """
    Monta a lista que será enviada ao Gemini contendo SOMENTE dados técnicos do
    controle — nunca nome da empresa, responsável ou qualquer dado identificável.
    """
    payload = []
    for l in lacunas:
        payload.append({
            "id": l["id"],
            "controle": l["controle"],
            "dimensao": l.get("dimensao", ""),
            "artigo": l["artigo"],
            "risco": l["risco"],
            "situacao_atual": l.get("resposta", ""),  # "Não" ou "Parcialmente"
            "recomendacao_base": l["recomendacao_base"],
        })
    return payload


def _montar_prompt(lacunas: list) -> str:
    """Concatena o prompt de sistema com a lista anonimizada de lacunas (JSON)."""
    lista_json = json.dumps(_anonimizar_lacunas(lacunas), ensure_ascii=False, indent=2)
    return PROMPT_SISTEMA + lista_json


def _extrair_json(texto: str):
    """
    Faz o parsing robusto da resposta do modelo.

    Mesmo pedindo JSON puro, alguns modelos eventualmente embrulham a saída em
    blocos markdown (```json ... ```). Esta função remove esses invólucros e
    tenta carregar o JSON; se ainda assim falhar, procura o primeiro array [...]
    no texto.
    """
    if not texto:
        return None

    limpo = texto.strip()

    # Remove cercas de código markdown, se houver.
    limpo = re.sub(r"^```(?:json)?\s*", "", limpo)
    limpo = re.sub(r"\s*```$", "", limpo)

    try:
        return json.loads(limpo)
    except json.JSONDecodeError:
        # Última tentativa: extrair o trecho entre o primeiro '[' e o último ']'.
        inicio, fim = limpo.find("["), limpo.rfind("]")
        if inicio != -1 and fim != -1 and fim > inicio:
            try:
                return json.loads(limpo[inicio:fim + 1])
            except json.JSONDecodeError:
                return None
    return None


def _chamar_gemini(prompt: str, modelo: str) -> str:
    """
    Faz UMA chamada ao Gemini com retry/backoff exponencial para o erro 429
    (ResourceExhausted) e para indisponibilidades temporárias (503).

    Retorna o texto bruto da resposta. Lança exceção se esgotar as tentativas.
    """
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

    # Força saída em JSON e baixa temperatura para respostas consistentes.
    config = genai.GenerationConfig(
        temperature=0.4,
        response_mime_type="application/json",
    )
    cliente = genai.GenerativeModel(modelo, generation_config=config)

    ultimo_erro = None
    for tentativa in range(MAX_TENTATIVAS):
        try:
            resposta = cliente.generate_content(prompt)
            return resposta.text
        except google_exceptions.ResourceExhausted as e:
            # Erro 429 — limite de requisições. Espera e tenta de novo.
            ultimo_erro = e
            espera = BACKOFF_BASE_SEG * (2 ** tentativa)
            print(f"[gemini] 429 rate limit. Aguardando {espera:.0f}s "
                  f"(tentativa {tentativa + 1}/{MAX_TENTATIVAS})...")
            time.sleep(espera)
        except google_exceptions.ServiceUnavailable as e:
            # Erro 503 — serviço temporariamente indisponível. Mesmo tratamento.
            ultimo_erro = e
            espera = BACKOFF_BASE_SEG * (2 ** tentativa)
            print(f"[gemini] 503 indisponível. Aguardando {espera:.0f}s "
                  f"(tentativa {tentativa + 1}/{MAX_TENTATIVAS})...")
            time.sleep(espera)

    # Esgotou as tentativas: propaga o último erro para acionar o fallback.
    raise RuntimeError(f"Falha ao chamar o Gemini após {MAX_TENTATIVAS} tentativas: {ultimo_erro}")


# ---------------------------------------------------------------------------
# Fallback determinístico (quando a IA não está disponível)
# ---------------------------------------------------------------------------

def _fallback_lacuna(lacuna: dict) -> dict:
    """
    Gera descrição e passos a partir da própria base de conhecimento, sem IA.
    Garante que o relatório saia completo mesmo sem acesso ao Gemini.
    """
    descricao = (
        f"Foi identificada uma lacuna no controle '{lacuna['controle']}' "
        f"({lacuna['artigo']}), classificada como risco {lacuna['risco']}. "
        f"A não conformidade pode expor a organização a sanções e a riscos aos "
        f"titulares de dados."
    )
    passos = [
        "Avaliar a situação atual do controle e mapear lacunas específicas.",
        f"Implementar a recomendação: {lacuna['recomendacao_base']}",
        "Documentar evidências da adequação e atribuir responsáveis.",
        "Revisar periodicamente o controle e atualizar conforme a ANPD.",
    ]
    return {"descricao": descricao, "passos": passos}


# ---------------------------------------------------------------------------
# Função pública principal
# ---------------------------------------------------------------------------

def redigir_lacunas(lacunas: list, modelo: str = None) -> dict:
    """
    Recebe a lista de lacunas do motor de regras e devolve a redação de cada uma.

    Retorna um dicionário:
        {
          "fonte": "gemini" | "fallback",
          "erro": None | "mensagem amigável",
          "itens": { "EC-001": {"descricao": "...", "passos": [...]}, ... }
        }

    Se não houver lacunas, retorna estrutura vazia. Se a API falhar ou não houver
    chave configurada, usa o fallback determinístico para TODAS as lacunas.
    """
    modelo = modelo or MODELO_PADRAO

    # Sem lacunas: nada a redigir (empresa em conformidade nos itens avaliados).
    if not lacunas:
        return {"fonte": "nenhuma", "erro": None, "itens": {}}

    # Sem chave de API: vai direto para o fallback, sem tentar a rede.
    if not api_disponivel():
        itens = {l["id"]: _fallback_lacuna(l) for l in lacunas}
        return {
            "fonte": "fallback",
            "erro": "Chave da API do Gemini não configurada (.env). "
                    "O relatório foi gerado com as recomendações da base de conhecimento.",
            "itens": itens,
        }

    # Tenta usar o Gemini.
    try:
        prompt = _montar_prompt(lacunas)
        texto = _chamar_gemini(prompt, modelo)
        dados = _extrair_json(texto)

        if not isinstance(dados, list):
            raise ValueError("Resposta do Gemini não é uma lista JSON válida.")

        # Indexa a resposta da IA por id do controle.
        por_id = {}
        for item in dados:
            if isinstance(item, dict) and "id" in item:
                por_id[item["id"]] = item

        # Monta o resultado final, com fallback POR ITEM caso algum id falte.
        itens = {}
        houve_fallback_parcial = False
        for l in lacunas:
            item = por_id.get(l["id"])
            descricao = (item or {}).get("descricao")
            passos = (item or {}).get("passos")
            if descricao and isinstance(passos, list) and passos:
                itens[l["id"]] = {"descricao": descricao.strip(), "passos": passos}
            else:
                itens[l["id"]] = _fallback_lacuna(l)
                houve_fallback_parcial = True

        return {
            "fonte": "gemini",
            "erro": ("Alguns itens usaram a recomendação da base por resposta "
                     "incompleta da IA." if houve_fallback_parcial else None),
            "itens": itens,
        }

    except Exception as e:
        # Qualquer falha (rede, 429 esgotado, parsing): cai no fallback total.
        itens = {l["id"]: _fallback_lacuna(l) for l in lacunas}
        return {
            "fonte": "fallback",
            "erro": f"Não foi possível redigir com a IA ({type(e).__name__}). "
                    f"O relatório foi gerado com as recomendações da base de conhecimento.",
            "itens": itens,
        }


# ---------------------------------------------------------------------------
# Autoteste — executado apenas com `python gemini_client.py`
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== AUTOTESTE DO CLIENTE GEMINI ===\n")
    print(f"Modelo configurado: {MODELO_PADRAO}")
    print(f"Chave de API presente: {'sim' if api_disponivel() else 'não'}\n")

    # Lacunas de exemplo (formato que o motor de regras produz).
    lacunas_exemplo = [
        {
            "id": "EC-003",
            "controle": "Gestão de consentimento e cookies com aceite granular",
            "dimensao": "Bases Legais e Consentimento",
            "artigo": "Art. 7, I e Art. 8 da LGPD",
            "risco": "alto",
            "resposta": "Não",
            "recomendacao_base": "Implementar banner de cookies com aceite e recusa por categoria.",
        },
        {
            "id": "EC-010",
            "controle": "Procedimento de notificação à ANPD e aos titulares",
            "dimensao": "Resposta a Incidentes",
            "artigo": "Art. 48 da LGPD e Res. CD/ANPD nº 15/2024",
            "risco": "medio",
            "resposta": "Parcialmente",
            "recomendacao_base": "Comunicar incidentes em 3 dias úteis conforme a Res. CD/ANPD nº 15/2024.",
        },
    ]

    resultado = redigir_lacunas(lacunas_exemplo)
    print(f"Fonte da redação: {resultado['fonte']}")
    if resultado["erro"]:
        print(f"Aviso: {resultado['erro']}")
    print()
    for cid, conteudo in resultado["itens"].items():
        print(f"[{cid}] {conteudo['descricao'][:120]}...")
        for i, passo in enumerate(conteudo["passos"], 1):
            print(f"   {i}. {passo[:100]}")
        print()
    print("Autoteste concluído.")
