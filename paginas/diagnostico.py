# -*- coding: utf-8 -*-
"""
paginas/diagnostico.py — Etapas 1 e 2 do fluxo.

  Etapa 1 (fase "dados"):        nome e setor da empresa.
  Etapa 2 (fase "questionario"): perguntas do setor, geradas SOMENTE depois que
                                 os dados da empresa foram preenchidos.

Ao gerar o diagnóstico, o resultado é guardado em st.session_state e o usuário
é levado à página exclusiva do relatório (paginas/relatorio.py).
"""

import streamlit as st

import ui
import motor_regras
import gemini_client

ss = st.session_state
ss.setdefault("fase", "dados")  # "dados" -> "questionario"


# ---------------------------------------------------------------------------
# Etapa 1 — Dados da empresa
# ---------------------------------------------------------------------------

def tela_dados():
    ui.stepper(1)

    st.markdown("## Vamos começar")
    st.caption(
        "Primeiro, identifique a empresa. O questionário será montado de acordo "
        "com o setor escolhido."
    )

    rotulo_para_chave = {v: k for k, v in motor_regras.SETORES.items()}
    rotulos = list(motor_regras.SETORES.values())
    indice = rotulos.index(ss["setor_rotulo"]) if ss.get("setor_rotulo") in rotulos else 0

    with st.container(border=True):
        with st.form("form_dados"):
            empresa = st.text_input(
                "Nome da empresa",
                value=ss.get("empresa", ""),
                placeholder="Ex.: Minha Empresa Ltda.",
            )
            setor_rotulo = st.selectbox("Setor de atuação", rotulos, index=indice)
            avancar = st.form_submit_button(
                "Continuar para o questionário  →", type="primary", use_container_width=True
            )

        if avancar:
            if not empresa or not empresa.strip():
                st.error("Informe o nome da empresa para continuar.")
            else:
                ss["empresa"] = empresa.strip()
                ss["setor_rotulo"] = setor_rotulo
                ss["setor"] = rotulo_para_chave[setor_rotulo]
                ss["fase"] = "questionario"
                st.rerun()


# ---------------------------------------------------------------------------
# Etapa 2 — Questionário
# ---------------------------------------------------------------------------

def tela_questionario():
    ui.stepper(2)

    # Faixa de contexto: lembra qual empresa/setor está sendo avaliado e permite voltar.
    info, acao = st.columns([4, 1.2])
    with info:
        st.markdown(f"**{ss['empresa']}**  ·  {ss['setor_rotulo']}")
    with acao:
        if st.button("✏️ Alterar", use_container_width=True):
            ss["fase"] = "dados"
            st.rerun()

    st.markdown("## Questionário")
    st.caption(
        "Responda com sinceridade — não existe resposta certa ou errada. "
        "Cada pergunta traz um exemplo prático para ajudar."
    )

    try:
        questionario = motor_regras.carregar_questionario(ss["setor"])
    except Exception as e:
        st.error(f"Não foi possível carregar o questionário do setor: {e}")
        st.stop()

    # Agrupa as perguntas por dimensão para exibir cada bloco em um "card".
    grupos: dict[str, list] = {}
    for p in questionario["perguntas"]:
        grupos.setdefault(p["dimensao"], []).append(p)

    respostas = {}
    with st.form("form_questionario"):
        for dimensao, perguntas in grupos.items():
            with st.container(border=True):
                st.markdown(f"#### {dimensao}")
                for pergunta in perguntas:
                    resposta = st.radio(
                        pergunta["pergunta"],
                        options=pergunta["opcoes"],
                        index=None,
                        key=f"{ss['setor']}__{pergunta['id']}",
                        help=pergunta.get("exemplo") or None,
                    )
                    if pergunta.get("exemplo"):
                        ui.exemplo(pergunta["exemplo"])
                    respostas[pergunta["id"]] = resposta

        enviado = st.form_submit_button(
            "🔍 Gerar diagnóstico  →", type="primary", use_container_width=True
        )

    if enviado:
        sem_resposta = [pid for pid, r in respostas.items() if r is None]
        if sem_resposta:
            st.error(
                f"Faltam {len(sem_resposta)} pergunta(s) sem resposta. "
                "Responda todas para um diagnóstico completo."
            )
            st.stop()

        try:
            with st.spinner("Analisando as respostas e calculando o score..."):
                diagnostico = motor_regras.gerar_diagnostico(ss["setor"], respostas)

            with st.spinner("Redigindo as recomendações (pode levar alguns segundos)..."):
                redacao = gemini_client.redigir_lacunas(diagnostico["lacunas"])

            with st.spinner("Gerando o relatório em PDF..."):
                import gerador_relatorio  # import lazy: erro de WeasyPrint vira mensagem clara
                pdf_bytes = gerador_relatorio.gerar_pdf(diagnostico, redacao, ss["empresa"])
                nome_pdf = gerador_relatorio.nome_arquivo_pdf(ss["empresa"], ss["setor"])

            ss["resultado"] = {
                "diagnostico": diagnostico,
                "redacao": redacao,
                "pdf_bytes": pdf_bytes,
                "nome_pdf": nome_pdf,
                "empresa": ss["empresa"],
            }
            st.switch_page("paginas/relatorio.py")

        except ImportError as e:
            st.error(
                "Falha ao carregar o gerador de PDF (WeasyPrint). No Windows, "
                "confirme a instalação do GTK3 Runtime. Detalhe: " + str(e)
            )
        except Exception as e:
            st.error(f"Ocorreu um erro ao gerar o diagnóstico: {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# Roteamento das etapas
# ---------------------------------------------------------------------------

if ss["fase"] == "questionario" and ss.get("setor"):
    tela_questionario()
else:
    tela_dados()
