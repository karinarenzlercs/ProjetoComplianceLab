# -*- coding: utf-8 -*-
"""
ui.py — Estilo e componentes visuais compartilhados entre as páginas.

Centraliza paleta, CSS global e pequenos componentes (selo de risco e o
"stepper" de progresso) para que app.py e as páginas tenham aparência
consistente, moderna e legível.
"""

import streamlit as st

# Identidade visual do dossiê: cru, editorial, monocromático com acento vermelho.
FUNDO = "#F5F2EC"       # papel/cream
TINTA = "#1A1714"       # texto quase preto
ACENTO = "#C1121F"      # vermelho de acento
MUTED = "#8A847A"       # texto secundário / rótulos
HAIRLINE = "#D8D2C6"    # fios finos sobre o fundo

# Níveis de risco no vocabulário monocromático da marca: o alto usa o acento,
# os demais ficam em tons discretos para não competir com ele.
COR_RISCO = {"alto": "#C1121F", "medio": "#8A6D00", "baixo": "#3A6B4A"}
ROTULO_RISCO = {"alto": "RISCO ALTO", "medio": "RISCO MÉDIO", "baixo": "RISCO BAIXO"}

# Rótulos das etapas do fluxo (usados pelo stepper).
ETAPAS = ["Dados da empresa", "Questionário", "Relatório"]

_CSS = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

  /* Aparência geral mais limpa: esconde o excesso de cromo do Streamlit. */
  [data-testid="stToolbar"] { display: none; }
  #MainMenu { visibility: hidden; }
  footer { visibility: hidden; }

  /* Fundo papel e tipografia base. */
  html, body, [data-testid="stAppViewContainer"], .stApp {
    background: #F5F2EC;
    color: #1A1714;
    font-family: 'Archivo', -apple-system, BlinkMacSystemFont, sans-serif;
  }
  .block-container { padding-top: 2.4rem; padding-bottom: 3.5rem; max-width: 880px; }

  /* Títulos editoriais: pretos, densos, levemente compactados. */
  h1, h2, h3, h4 {
    color: #1A1714;
    font-family: 'Archivo', sans-serif;
    font-weight: 800;
    letter-spacing: -.01em;
  }
  h1 { letter-spacing: -.02em; }

  /* Rótulos e código em mono. */
  code, kbd, pre, .mono { font-family: 'IBM Plex Mono', ui-monospace, monospace; }

  a { color: #C1121F; }

  /* ---------- Stepper: numeração de documento (01 02 03) ---------- */
  .stepper {
    display: flex;
    align-items: stretch;
    gap: 0;
    margin: .2rem 0 2rem 0;
    border-top: 1px solid #D8D2C6;
    border-bottom: 1px solid #D8D2C6;
  }
  .stepper .step {
    flex: 1;
    display: flex;
    align-items: baseline;
    gap: 10px;
    padding: 12px 14px;
    border-left: 1px solid #D8D2C6;
  }
  .stepper .step:first-child { border-left: none; }
  .stepper .num {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 15px; font-weight: 600;
    letter-spacing: 1px;
    color: #8A847A;
  }
  .stepper .rotulo {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px; font-weight: 500;
    letter-spacing: .12em; text-transform: uppercase;
    color: #8A847A;
  }
  /* Etapa atual: tinta cheia + acento vermelho no número. */
  .stepper .step.ativo { border-top: 2px solid #C1121F; margin-top: -1px; }
  .stepper .step.ativo .num { color: #C1121F; }
  .stepper .step.ativo .rotulo { color: #1A1714; }
  /* Etapas concluídas: tinta cheia, sem destaque de acento. */
  .stepper .step.feito .num { color: #1A1714; }
  .stepper .step.feito .rotulo { color: #1A1714; }

  /* Selo de risco: etiqueta quadrada com fio fino, em mono maiúsculo. */
  .selo-risco {
    display: inline-block;
    font-family: 'IBM Plex Mono', monospace;
    font-size: .7rem; font-weight: 600;
    letter-spacing: .1em; text-transform: uppercase;
    padding: 2px 8px;
    border: 1px solid currentColor;
    background: transparent;
  }

  /* Exemplo de cada pergunta: fio fino à esquerda, sem preenchimento. */
  .exemplo {
    font-size: .82rem; color: #5c574f;
    border-left: 2px solid #C1121F;
    padding: 4px 0 4px 12px;
    margin: 2px 0 6px 0;
  }

  /* Botões retos: sem raio, sem sombra, contorno em fio fino. */
  .stButton button, .stDownloadButton button {
    border-radius: 0;
    border: 1px solid #1A1714;
    background: #1A1714;
    color: #F5F2EC;
    font-family: 'IBM Plex Mono', monospace;
    font-weight: 500;
    letter-spacing: .04em;
    box-shadow: none;
  }
  .stButton button:hover, .stDownloadButton button:hover {
    background: #C1121F; border-color: #C1121F; color: #F5F2EC;
  }

  /* Campos de entrada em fio fino, cantos retos. */
  [data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"] > div {
    border-radius: 0 !important;
  }

  /* ---------- Sidebar: mesmo papel, fonte Archivo, sem azul ---------- */
  [data-testid="stSidebar"] {
    background: #F5F2EC;
    border-right: 1px solid #D8D2C6;
  }
  [data-testid="stSidebar"] * {
    font-family: 'Archivo', sans-serif;
    color: #1A1714;
  }
  /* Neutraliza o azul padrão do Streamlit em links/itens da navegação. */
  [data-testid="stSidebar"] a,
  [data-testid="stSidebarNav"] a,
  [data-testid="stSidebarNav"] a span {
    color: #1A1714 !important;
  }
  [data-testid="stSidebarNav"] a:hover span { color: #C1121F !important; }

  /* Título fixo da sidebar: "COMPLIANCE LAB" em IBM Plex Mono caixa alta. */
  [data-testid="stSidebarNav"]::before {
    content: "COMPLIANCE LAB";
    display: block;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 13px; font-weight: 600;
    letter-spacing: .22em; text-transform: uppercase;
    color: #1A1714;
    padding: 8px 16px 14px 16px;
    margin-bottom: 6px;
    border-bottom: 1px solid #D8D2C6;
  }

  /* ---------- Botão primário: retângulo tinta cheia, texto branco ---------- */
  [data-testid="stBaseButton-primary"],
  .stButton button[kind="primary"],
  button[data-testid="baseButton-primary"] {
    border-radius: 0 !important;
    background: #1A1714 !important;
    border: 1px solid #1A1714 !important;
    color: #FFFFFF !important;
    box-shadow: none !important;
    font-family: 'IBM Plex Mono', monospace;
    font-weight: 600;
    letter-spacing: .04em;
  }
  [data-testid="stBaseButton-primary"]:hover,
  .stButton button[kind="primary"]:hover,
  button[data-testid="baseButton-primary"]:hover {
    background: #C1121F !important;
    border-color: #C1121F !important;
    color: #FFFFFF !important;
  }

  /* ---------- Bloco de formulário (st.form): reto, sem sombra ---------- */
  [data-testid="stForm"] {
    border-radius: 0 !important;
    box-shadow: none !important;
    border: 1px solid #D8D2C6;
    background: transparent;
  }
</style>
"""


def aplicar_estilo():
    """Injeta o CSS global. Deve ser chamado uma vez por execução de página."""
    st.markdown(_CSS, unsafe_allow_html=True)


def selo_risco(risco: str) -> str:
    """Devolve um selo HTML (etiqueta com fio fino) para o nível de risco."""
    cor = COR_RISCO.get(risco, TINTA)
    rotulo = ROTULO_RISCO.get(risco, risco.upper())
    return f"<span class='selo-risco' style='color:{cor};'>{rotulo}</span>"


def exemplo(texto: str):
    """Renderiza o exemplo prático de uma pergunta com destaque sutil."""
    st.markdown(f"<div class='exemplo'>💡 {texto}</div>", unsafe_allow_html=True)


def stepper(atual: int):
    """
    Renderiza a barra de progresso por etapas (1, 2 ou 3).

    Estilo de numeração de documento (01, 02, 03): a etapa atual recebe o fio de
    acento e o número em vermelho; as concluídas ficam em tinta cheia e as
    seguintes em cinza. Dá ao usuário a noção de onde está e quanto falta.
    """
    partes = []
    for i, nome in enumerate(ETAPAS, 1):
        estado = "feito" if i < atual else ("ativo" if i == atual else "")
        partes.append(
            f"<div class='step {estado}'>"
            f"<span class='num'>{i:02d}</span>"
            f"<span class='rotulo'>{nome}</span></div>"
        )
    st.markdown(f"<div class='stepper'>{''.join(partes)}</div>", unsafe_allow_html=True)
