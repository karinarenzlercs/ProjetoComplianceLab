# -*- coding: utf-8 -*-
"""
ui.py — Estilo e componentes visuais compartilhados entre as páginas.

Centraliza paleta, CSS global e pequenos componentes (selo de risco e o
"stepper" de progresso) para que app.py e as páginas tenham aparência
consistente, moderna e legível.
"""

import streamlit as st

# Paleta da identidade visual (mesma do relatório PDF).
AZUL_ESCURO = "#1F4E79"
AZUL = "#2E75B6"

COR_RISCO = {"alto": "#A32D2D", "medio": "#C77700", "baixo": "#2E7D32"}
ROTULO_RISCO = {"alto": "RISCO ALTO", "medio": "RISCO MÉDIO", "baixo": "RISCO BAIXO"}

# Rótulos das etapas do fluxo (usados pelo stepper).
ETAPAS = ["Dados da empresa", "Questionário", "Relatório"]

_CSS = """
<style>
  /* Aparência geral mais limpa: esconde o excesso de cromo do Streamlit. */
  [data-testid="stToolbar"] { display: none; }
  #MainMenu { visibility: hidden; }
  footer { visibility: hidden; }
  .block-container { padding-top: 2.2rem; padding-bottom: 3rem; }

  /* Títulos com a cor da marca. */
  h1, h2, h3 { color: #1F4E79; }

  /* ---------- Stepper de progresso ---------- */
  .stepper {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-wrap: wrap;
    gap: 8px;
    margin: .4rem 0 1.6rem 0;
  }
  .stepper .step { display: flex; align-items: center; gap: 8px; }
  .stepper .bolinha {
    width: 32px; height: 32px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 14px;
    background: #E6ECF3; color: #8195AC;
    border: 2px solid #E6ECF3;
    transition: all .2s ease;
  }
  .stepper .rotulo { font-size: 13px; font-weight: 600; color: #8195AC; }
  .stepper .step.ativo .bolinha {
    background: #2E75B6; color: #fff; border-color: #2E75B6;
    box-shadow: 0 0 0 4px rgba(46,117,182,.16);
  }
  .stepper .step.ativo .rotulo { color: #1F4E79; }
  .stepper .step.feito .bolinha { background: #2E7D32; color: #fff; border-color: #2E7D32; }
  .stepper .step.feito .rotulo { color: #2E7D32; }
  .stepper .linha { width: 34px; height: 2px; background: #E6ECF3; border-radius: 2px; }
  .stepper .linha.feito { background: #2E7D32; }

  /* Selo de risco usado na tela. */
  .selo-risco {
    color: #fff; padding: 2px 9px; border-radius: 4px;
    font-size: .72rem; font-weight: 700; letter-spacing: .3px;
  }

  /* Realce sutil para o exemplo de cada pergunta. */
  .exemplo {
    font-size: .82rem; color: #5b6b7e;
    background: #F4F7FB; border-left: 3px solid #2E75B6;
    padding: 6px 10px; border-radius: 4px; margin: 2px 0 4px 0;
  }

  /* Botões um pouco mais "cheios". */
  .stButton button, .stDownloadButton button { border-radius: 8px; font-weight: 600; }
</style>
"""


def aplicar_estilo():
    """Injeta o CSS global. Deve ser chamado uma vez por execução de página."""
    st.markdown(_CSS, unsafe_allow_html=True)


def selo_risco(risco: str) -> str:
    """Devolve um selo HTML colorido para o nível de risco."""
    cor = COR_RISCO.get(risco, AZUL)
    rotulo = ROTULO_RISCO.get(risco, risco.upper())
    return f"<span class='selo-risco' style='background:{cor};'>{rotulo}</span>"


def exemplo(texto: str):
    """Renderiza o exemplo prático de uma pergunta com destaque sutil."""
    st.markdown(f"<div class='exemplo'>💡 {texto}</div>", unsafe_allow_html=True)


def stepper(atual: int):
    """
    Renderiza a barra de progresso por etapas (1, 2 ou 3).

    Etapas anteriores aparecem como concluídas (✓), a atual em destaque e as
    seguintes apagadas. Dá ao usuário a noção de onde está e quanto falta.
    """
    partes = []
    for i, nome in enumerate(ETAPAS, 1):
        estado = "feito" if i < atual else ("ativo" if i == atual else "")
        marca = "✓" if i < atual else str(i)
        partes.append(
            f"<div class='step {estado}'>"
            f"<div class='bolinha'>{marca}</div>"
            f"<div class='rotulo'>{nome}</div></div>"
        )
        if i < len(ETAPAS):
            partes.append(f"<div class='linha {'feito' if i < atual else ''}'></div>")
    st.markdown(f"<div class='stepper'>{''.join(partes)}</div>", unsafe_allow_html=True)
