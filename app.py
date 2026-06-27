# -*- coding: utf-8 -*-
"""
app.py — Ponto de entrada do Diagnóstico de Maturidade LGPD (Streamlit).

Define a configuração da página, o estilo global, a barra lateral informativa
e a NAVEGAÇÃO entre páginas dedicadas:

  - paginas/diagnostico.py — coleta dos dados da empresa e o questionário.
  - paginas/relatorio.py   — página exclusiva do relatório gerado.

O fluxo entre etapas é controlado por st.session_state e por st.switch_page,
de modo que o relatório tenha sua própria página.

Rodar localmente:   streamlit run app.py
"""

import streamlit as st

import ui

# ---------------------------------------------------------------------------
# Configuração geral da página
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Diagnóstico de Maturidade LGPD",
    page_icon="🛡️",
    layout="centered",
    initial_sidebar_state="expanded",
)

ui.aplicar_estilo()


# ---------------------------------------------------------------------------
# Barra lateral — informações sobre a ferramenta (sem status técnico da IA)
# ---------------------------------------------------------------------------

def barra_lateral():
    with st.sidebar:
        st.markdown("### 🛡️ Diagnóstico LGPD")
        st.caption("Maturidade em proteção de dados")
        st.divider()

        st.markdown("#### O que é")
        st.write(
            "Uma ferramenta gratuita que avalia o quanto a sua empresa está "
            "adequada à **LGPD** e às **resoluções da ANPD**. Ao final, você "
            "recebe um relatório em PDF com o seu nível de maturidade e um "
            "plano de ação prático."
        )

        st.markdown("#### Como funciona")
        st.markdown(
            "1. **Identificação** — informe o nome e o setor da empresa\n"
            "2. **Questionário** — responda a perguntas simples, com exemplos\n"
            "3. **Relatório** — baixe o diagnóstico com o passo a passo"
        )

        st.markdown("#### Para quem é")
        st.markdown(
            "- ⚖️ Escritórios de advocacia\n"
            "- 💻 Empresas de tecnologia / SaaS\n"
            "- 🛒 E-commerce"
        )

        st.divider()
        st.caption(
            "Diagnóstico **orientativo**: não constitui parecer jurídico nem "
            "substitui o Encarregado (DPO). Base normativa: LGPD (Lei nº "
            "13.709/2018) e Resoluções CD/ANPD nº 15, 18 e 19/2024."
        )


barra_lateral()


# ---------------------------------------------------------------------------
# Navegação entre páginas (a do relatório é exclusiva)
# ---------------------------------------------------------------------------

pagina_diagnostico = st.Page(
    "paginas/diagnostico.py", title="Diagnóstico", icon="📝", default=True
)
pagina_relatorio = st.Page(
    "paginas/relatorio.py", title="Relatório", icon="📄"
)

# position="hidden": escondemos o menu de navegação nativo — o fluxo entre as
# páginas é guiado pelos botões do próprio diagnóstico.
navegacao = st.navigation([pagina_diagnostico, pagina_relatorio], position="hidden")
navegacao.run()
