# -*- coding: utf-8 -*-
"""
app.py — Interface web (Streamlit) do Diagnóstico de Maturidade LGPD.

Orquestra as duas camadas:
  1) motor_regras  — diagnóstico determinístico (score + lacunas).
  2) gemini_client — redação das lacunas (com fallback).
  3) gerador_relatorio — monta o PDF final para download.

Rodar localmente:   streamlit run app.py
"""

import streamlit as st

import motor_regras
import gemini_client

# ---------------------------------------------------------------------------
# Configuração geral da página
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Diagnóstico de Maturidade LGPD",
    page_icon="🛡️",
    layout="centered",
)

# Cores da identidade visual (mesmas do relatório PDF).
AZUL_ESCURO = "#1F4E79"
AZUL = "#2E75B6"

# Mapa de cor por nível de risco, para os "selos" exibidos na tela.
COR_RISCO = {"alto": "#A32D2D", "medio": "#C77700", "baixo": "#2E7D32"}
ROTULO_RISCO = {"alto": "RISCO ALTO", "medio": "RISCO MÉDIO", "baixo": "RISCO BAIXO"}


# ---------------------------------------------------------------------------
# Funções auxiliares de interface
# ---------------------------------------------------------------------------

def selo_risco(risco: str) -> str:
    """Devolve um selo HTML colorido para o nível de risco."""
    cor = COR_RISCO.get(risco, AZUL)
    rotulo = ROTULO_RISCO.get(risco, risco.upper())
    return (
        f"<span style='background:{cor};color:#fff;padding:2px 8px;"
        f"border-radius:4px;font-size:0.75rem;font-weight:bold;'>{rotulo}</span>"
    )


def cabecalho():
    """Renderiza o título e a descrição do app."""
    st.markdown(
        f"<h1 style='color:{AZUL_ESCURO};margin-bottom:0;'>🛡️ Diagnóstico de Maturidade LGPD</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<p style='color:{AZUL};font-weight:bold;margin-top:0;'>"
        "Avalie a conformidade da sua empresa e gere um relatório com plano de ação.</p>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Responda ao questionário do seu setor. O diagnóstico é determinístico "
        "(baseado em norma); a IA apenas redige as recomendações já validadas."
    )


def barra_lateral():
    """Mostra informações de status na barra lateral."""
    with st.sidebar:
        st.header("Sobre")
        st.write(
            "Plataforma de diagnóstico de conformidade com a **LGPD** e as "
            "**resoluções da ANPD**, para os setores Jurídico, Tecnologia e E-commerce."
        )
        st.divider()
        st.subheader("Status da IA (Gemini)")
        if gemini_client.api_disponivel():
            st.success("Chave da API configurada. As recomendações serão redigidas pela IA.")
        else:
            st.warning(
                "Sem chave da API do Gemini. O relatório será gerado com as "
                "recomendações da base de conhecimento (modo fallback)."
            )
        st.caption(f"Modelo: {gemini_client.MODELO_PADRAO}")


# ---------------------------------------------------------------------------
# Fluxo principal
# ---------------------------------------------------------------------------

def main():
    cabecalho()
    barra_lateral()

    # ----- Dados da empresa e setor -----
    st.subheader("1. Dados da empresa")
    col1, col2 = st.columns([2, 1.5])
    with col1:
        empresa = st.text_input("Nome da empresa", placeholder="Ex.: Minha Empresa Ltda.")
    with col2:
        # O usuário escolhe pelo rótulo amigável; convertemos para a chave interna.
        rotulo_para_chave = {v: k for k, v in motor_regras.SETORES.items()}
        setor_rotulo = st.selectbox("Setor", list(motor_regras.SETORES.values()))
        setor = rotulo_para_chave[setor_rotulo]

    # ----- Questionário dinâmico -----
    st.subheader("2. Questionário")
    st.caption(f"Setor selecionado: **{setor_rotulo}**. Responda todas as perguntas.")

    try:
        questionario = motor_regras.carregar_questionario(setor)
    except Exception as e:
        st.error(f"Não foi possível carregar o questionário do setor: {e}")
        st.stop()

    # Coleta as respostas dentro de um formulário (evita recarregar a cada clique).
    respostas = {}
    with st.form("form_diagnostico"):
        dimensao_atual = None
        for pergunta in questionario["perguntas"]:
            # Imprime um subtítulo sempre que muda a dimensão (perguntas já vêm ordenadas).
            if pergunta["dimensao"] != dimensao_atual:
                dimensao_atual = pergunta["dimensao"]
                st.markdown(f"#### {dimensao_atual}")

            # index=None faz o rádio começar sem seleção, exigindo resposta consciente.
            # O `help` mostra um exemplo curto e prático para orientar quem responde.
            resposta = st.radio(
                pergunta["pergunta"],
                options=pergunta["opcoes"],
                index=None,
                key=f"{setor}__{pergunta['id']}",  # chave única por setor+pergunta
                help=pergunta.get("exemplo") or None,
            )
            # Exibe o exemplo também abaixo da pergunta (não só no ícone de ajuda),
            # para facilitar a compreensão de quem não tem conhecimento técnico.
            if pergunta.get("exemplo"):
                st.caption(f"💡 {pergunta['exemplo']}")
            respostas[pergunta["id"]] = resposta

        enviado = st.form_submit_button("🔍 Gerar diagnóstico", type="primary")

    # ----- Processamento ao enviar -----
    if enviado:
        # Validação 1: nome da empresa preenchido.
        if not empresa or not empresa.strip():
            st.error("Por favor, informe o nome da empresa antes de gerar o diagnóstico.")
            st.stop()

        # Validação 2: todas as perguntas respondidas.
        sem_resposta = [pid for pid, r in respostas.items() if r is None]
        if sem_resposta:
            st.error(
                f"Faltam {len(sem_resposta)} pergunta(s) sem resposta. "
                "Responda todas para um diagnóstico completo."
            )
            st.stop()

        # Pipeline: motor -> Gemini -> PDF. Cada etapa com tratamento de erro.
        try:
            with st.spinner("Analisando respostas e calculando o score..."):
                diagnostico = motor_regras.gerar_diagnostico(setor, respostas)

            with st.spinner("Redigindo as recomendações (pode levar alguns segundos)..."):
                redacao = gemini_client.redigir_lacunas(diagnostico["lacunas"])

            with st.spinner("Gerando o relatório em PDF..."):
                # Import lazy: se houver problema com o WeasyPrint/GTK, vira mensagem clara.
                import gerador_relatorio
                pdf_bytes = gerador_relatorio.gerar_pdf(diagnostico, redacao, empresa)
                nome_pdf = gerador_relatorio.nome_arquivo_pdf(empresa, setor)

            # Guarda tudo na sessão para sobreviver ao rerun do botão de download.
            st.session_state["resultado"] = {
                "diagnostico": diagnostico,
                "redacao": redacao,
                "pdf_bytes": pdf_bytes,
                "nome_pdf": nome_pdf,
                "empresa": empresa,
            }
        except ImportError as e:
            st.error(
                "Falha ao carregar o gerador de PDF (WeasyPrint). No Windows, "
                "confirme a instalação do GTK3 Runtime. Detalhe: " + str(e)
            )
            st.stop()
        except Exception as e:
            st.error(f"Ocorreu um erro ao gerar o diagnóstico: {type(e).__name__}: {e}")
            st.stop()

    # ----- Exibição dos resultados (persistem na sessão) -----
    if "resultado" in st.session_state:
        exibir_resultado(st.session_state["resultado"])


def exibir_resultado(resultado: dict):
    """Mostra na tela o score, o resumo de lacunas e o botão de download do PDF."""
    diag = resultado["diagnostico"]
    redacao = resultado["redacao"]

    st.divider()
    st.subheader("3. Resultado do diagnóstico")

    # Score e nível em destaque.
    col1, col2, col3 = st.columns(3)
    col1.metric("Score de maturidade", f"{diag['score']}%")
    col2.metric("Nível", diag["nivel"])
    col3.metric("Lacunas identificadas", diag["total_lacunas"])

    # Barra de progresso do score (0–100).
    st.progress(int(round(diag["score"])))

    # Aviso se a redação caiu no fallback (sem IA) ou teve algum problema.
    if redacao.get("fonte") == "fallback":
        st.info(
            "ℹ️ As recomendações foram geradas a partir da base de conhecimento "
            "(sem IA). " + (redacao.get("erro") or "")
        )
    elif redacao.get("erro"):
        st.warning(redacao["erro"])

    # Resumo por risco.
    rr = diag["resumo_risco"]
    st.markdown(
        f"{selo_risco('alto')} &nbsp; **{rr['alto']}** &nbsp;&nbsp; "
        f"{selo_risco('medio')} &nbsp; **{rr['medio']}** &nbsp;&nbsp; "
        f"{selo_risco('baixo')} &nbsp; **{rr['baixo']}**",
        unsafe_allow_html=True,
    )

    # Botão de download do PDF.
    st.download_button(
        label="⬇️ Baixar relatório em PDF",
        data=resultado["pdf_bytes"],
        file_name=resultado["nome_pdf"],
        mime="application/pdf",
        type="primary",
    )

    # Pré-visualização das lacunas (mesmo conteúdo do PDF).
    if diag["lacunas"]:
        st.markdown("#### Lacunas e plano de ação")
        itens = redacao.get("itens", {})
        for i, lac in enumerate(diag["lacunas"], 1):
            red = itens.get(lac["id"], {})
            descricao = red.get("descricao") or lac["recomendacao_base"]
            passos = red.get("passos") or [lac["recomendacao_base"]]

            with st.expander(f"{i}. {lac['controle']}  —  {ROTULO_RISCO.get(lac['risco'])}"):
                st.markdown(selo_risco(lac["risco"]), unsafe_allow_html=True)
                st.caption(f"{lac['dimensao']} · {lac['artigo']}")
                # Rastreabilidade: mostra a pergunta avaliada e a resposta dada,
                # deixando claro por que este item virou uma lacuna.
                if lac.get("pergunta"):
                    st.caption(f"Pergunta avaliada: {lac['pergunta']}")
                if lac.get("resposta"):
                    st.markdown(f"**Sua resposta:** {lac['resposta']}")
                st.write(descricao)
                st.markdown("**Passo a passo para adequação:**")
                for n, passo in enumerate(passos, 1):
                    st.markdown(f"{n}. {passo}")

        # Apêndice na tela: todas as respostas, para conferência e auditoria.
        detalhe = diag.get("detalhe_respostas", [])
        if detalhe:
            with st.expander("📋 Conferir todas as respostas informadas"):
                st.caption(
                    "Reproduz exatamente o que foi respondido, na ordem do "
                    "questionário. O diagnóstico acima decorre apenas destas respostas."
                )
                dimensao_atual = None
                for r in detalhe:
                    if r["dimensao"] != dimensao_atual:
                        dimensao_atual = r["dimensao"]
                        st.markdown(f"**{dimensao_atual}**")
                    st.markdown(f"- {r['pergunta']}  \n  → **{r['resposta']}**")
    else:
        st.success(
            "Parabéns! Nenhuma lacuna foi identificada nos controles avaliados. "
            "Mantenha o monitoramento contínuo."
        )


if __name__ == "__main__":
    main()
