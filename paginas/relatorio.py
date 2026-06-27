# -*- coding: utf-8 -*-
"""
paginas/relatorio.py — Etapa 3 do fluxo: página exclusiva do relatório.

Mostra o resultado do diagnóstico como um painel: score em destaque, resumo de
risco, download do PDF, lacunas com plano de ação e o apêndice com todas as
respostas (rastreabilidade). Se o usuário chegar aqui sem ter gerado um
diagnóstico, é convidado a iniciar o fluxo.
"""

import streamlit as st

import ui

ss = st.session_state

ui.stepper(3)

# ---------------------------------------------------------------------------
# Sem resultado: orienta o usuário a iniciar o diagnóstico.
# ---------------------------------------------------------------------------

if "resultado" not in ss:
    st.info("Nenhum diagnóstico foi gerado ainda. Comece preenchendo os dados da empresa.")
    if st.button("← Iniciar diagnóstico", type="primary"):
        ss["fase"] = "dados"
        st.switch_page("paginas/diagnostico.py")
    st.stop()


resultado = ss["resultado"]
diag = resultado["diagnostico"]
redacao = resultado["redacao"]

# ---------------------------------------------------------------------------
# Cabeçalho + download do PDF
# ---------------------------------------------------------------------------

topo_esq, topo_dir = st.columns([3, 1.4])
with topo_esq:
    st.markdown("## 📄 Relatório de Diagnóstico")
    st.markdown(f"**{resultado['empresa']}**  ·  {diag.get('setor_nome', '')}")
with topo_dir:
    st.write("")
    st.download_button(
        "⬇️ Baixar PDF",
        data=resultado["pdf_bytes"],
        file_name=resultado["nome_pdf"],
        mime="application/pdf",
        type="primary",
        use_container_width=True,
    )

# ---------------------------------------------------------------------------
# Painel de score
# ---------------------------------------------------------------------------

with st.container(border=True):
    m1, m2, m3 = st.columns(3)
    m1.metric("Score de maturidade", f"{diag['score']}%")
    m2.metric("Nível", diag["nivel"])
    m3.metric("Lacunas identificadas", diag["total_lacunas"])

    st.progress(int(round(diag["score"])))

    rr = diag["resumo_risco"]
    st.markdown(
        f"{ui.selo_risco('alto')} &nbsp; **{rr['alto']}** &nbsp;&nbsp; "
        f"{ui.selo_risco('medio')} &nbsp; **{rr['medio']}** &nbsp;&nbsp; "
        f"{ui.selo_risco('baixo')} &nbsp; **{rr['baixo']}**",
        unsafe_allow_html=True,
    )

# Aviso sobre a fonte da redação (IA ou base de conhecimento).
if redacao.get("fonte") == "fallback":
    st.info(
        "ℹ️ As recomendações foram geradas a partir da base de conhecimento. "
        + (redacao.get("erro") or "")
    )
elif redacao.get("erro"):
    st.warning(redacao["erro"])

# ---------------------------------------------------------------------------
# Lacunas e plano de ação
# ---------------------------------------------------------------------------

if diag["lacunas"]:
    st.markdown("### Lacunas e plano de ação")
    itens = redacao.get("itens", {})
    for i, lac in enumerate(diag["lacunas"], 1):
        red = itens.get(lac["id"], {})
        descricao = red.get("descricao") or lac["recomendacao_base"]
        passos = red.get("passos") or [lac["recomendacao_base"]]

        with st.expander(f"{i}. {lac['controle']}  —  {ui.ROTULO_RISCO.get(lac['risco'])}"):
            st.markdown(ui.selo_risco(lac["risco"]), unsafe_allow_html=True)
            st.caption(f"{lac['dimensao']} · {lac['artigo']}")
            # Rastreabilidade: pergunta avaliada e resposta dada.
            if lac.get("pergunta"):
                st.caption(f"Pergunta avaliada: {lac['pergunta']}")
            if lac.get("resposta"):
                st.markdown(f"**Sua resposta:** {lac['resposta']}")
            st.write(descricao)
            st.markdown("**Passo a passo para adequação:**")
            for n, passo in enumerate(passos, 1):
                st.markdown(f"{n}. {passo}")
else:
    st.success(
        "Parabéns! Nenhuma lacuna foi identificada nos controles avaliados. "
        "Mantenha o monitoramento contínuo."
    )

# ---------------------------------------------------------------------------
# Apêndice: todas as respostas (conferência / auditoria)
# ---------------------------------------------------------------------------

detalhe = diag.get("detalhe_respostas", [])
if detalhe:
    with st.expander("📋 Conferir todas as respostas informadas"):
        st.caption(
            "Reproduz exatamente o que foi respondido, na ordem do questionário. "
            "O diagnóstico acima decorre apenas destas respostas."
        )
        dimensao_atual = None
        for r in detalhe:
            if r["dimensao"] != dimensao_atual:
                dimensao_atual = r["dimensao"]
                st.markdown(f"**{dimensao_atual}**")
            st.markdown(f"- {r['pergunta']}  \n  → **{r['resposta']}**")

# ---------------------------------------------------------------------------
# Recomeçar
# ---------------------------------------------------------------------------

st.divider()
if st.button("🔄 Fazer um novo diagnóstico"):
    for chave in ["resultado", "fase", "empresa", "setor", "setor_rotulo"]:
        ss.pop(chave, None)
    st.switch_page("paginas/diagnostico.py")
