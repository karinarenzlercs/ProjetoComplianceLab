# Relatório Técnico — Diagnóstico de Maturidade LGPD

**Projeto:** Diagnóstico de Conformidade LGPD / GRC — ProjetoComplianceLab
**Data do relatório:** 27/06/2026
**Branch:** main

---

## 1. Visão Geral

Plataforma web em Python que automatiza o diagnóstico de conformidade com a **LGPD (Lei nº 13.709/2018)** e as **Resoluções da ANPD (nº 15, 18 e 19/2024)**. O usuário preenche um questionário setorial e recebe um **relatório profissional em PDF** com score de maturidade, lacunas identificadas e plano de ação detalhado.

---

## 2. Principais Recursos

| Recurso | Descrição |
|---|---|
| Questionário dinâmico por setor | Perguntas organizadas em até 7 dimensões de governança de privacidade, específicas por tipo de organização |
| Score de maturidade | Cálculo determinístico (média simples) com 4 níveis: Inicial (0–30%), Em Desenvolvimento (31–60%), Intermediário (61–85%), Avançado (86–100%) |
| Identificação de lacunas | Cruza respostas "Não" e "Parcialmente" com a base de controles, vinculando cada lacuna a artigo da LGPD e nível de risco (alto / médio / baixo) |
| Redação de recomendações com IA | Usa Google Gemini Flash para redigir a descrição do risco e um passo a passo acionável de cada lacuna em linguagem acessível |
| Fallback determinístico | Se o Gemini estiver indisponível ou sem chave configurada, o relatório é gerado integralmente com as recomendações da base de conhecimento |
| Relatório em PDF | Gerado via Jinja2 + WeasyPrint, com cabeçalho, score visual, lacunas ordenadas por risco, apêndice de rastreabilidade e disclaimer jurídico |
| Apêndice de rastreabilidade | Todas as respostas do questionário são registradas no relatório, permitindo auditoria da correspondência entre resposta e diagnóstico |
| Base de conhecimento versionada | JSONs curados por setor, com campo de versão e data de revisão, alinhados às resoluções vigentes da ANPD |

### 2.1 Setores suportados

| Chave interna | Rótulo exibido |
|---|---|
| `juridico` | Escritório de Advocacia |
| `tecnologia` | Empresa de Tecnologia / SaaS |
| `ecommerce` | E-commerce |

### 2.2 Dimensões do questionário (exemplo — E-commerce)

- Governança e Encarregado (DPO)
- Bases Legais e Consentimento
- Direitos dos Titulares
- Segurança da Informação
- Transferência Internacional de Dados
- Contratos com Fornecedores / Operadores
- Resposta a Incidentes

---

## 3. Stack Tecnológica

| Camada | Tecnologia | Versão | Função |
|---|---|---|---|
| Interface web | **Streamlit** | 1.40.2 | Framework de aplicação web e gerenciamento de estado |
| IA generativa | **Google Generative AI** (`google-generativeai`) | 0.8.3 | Integração com a API Gemini Flash para redação das recomendações |
| Template de relatório | **Jinja2** | 3.1.4 | Renderização do template HTML do relatório com dados do diagnóstico |
| Geração de PDF | **WeasyPrint** | 63.1 | Conversão do HTML renderizado para PDF profissional |
| Variáveis de ambiente | **python-dotenv** | 1.0.1 | Carregamento seguro da chave da API a partir do `.env` |
| Runtime | **Python** | 3.12+ | Linguagem base do projeto |
| Deps de sistema (Linux/deploy) | GTK3 / Pango / Cairo / HarfBuzz | — | Bibliotecas de renderização exigidas pelo WeasyPrint no Streamlit Cloud |

### 2.1 Modelo de IA

- **Padrão:** `gemini-2.5-flash` (configurável via `GEMINI_MODEL` no `.env`)
- **Temperatura:** 0.4 (respostas consistentes e reprodutíveis)
- **Formato de saída forçado:** `application/json`
- **Política de retry:** backoff exponencial (2 s, 4 s, 8 s, 16 s) para erros 429 e 503

---

## 4. Arquitetura em Duas Camadas

```
Usuário
  │
  ▼
[Streamlit UI]  ←  app.py + paginas/diagnostico.py + paginas/relatorio.py
  │
  ├─ Camada 1 — Motor de Regras (DETERMINÍSTICO)
  │     motor_regras.py
  │     ├── carrega base_conhecimento/<setor>.json  (controles + artigos)
  │     ├── carrega questionarios/<setor>.json      (perguntas + dimensões)
  │     ├── calcula score de maturidade
  │     └── identifica lacunas (sem IA — 100% auditável)
  │
  ├─ Camada 2 — Redação com IA (ADITIVA)
  │     gemini_client.py
  │     ├── recebe apenas dados técnicos anônimos do controle
  │     ├── chama API Google Gemini Flash
  │     └── devolve descrição do risco + passo a passo de adequação
  │         (fallback determinístico se API indisponível)
  │
  └─ Geração do PDF
        gerador_relatorio.py
        ├── mescla saída da Camada 1 + Camada 2
        ├── renderiza templates/relatorio.html via Jinja2
        └── converte para PDF via WeasyPrint (bytes em memória)
```

**Princípio fundamental:** a Camada 2 (IA) apenas *redige* — ela nunca enquadra artigos ou define riscos. Todo o conteúdo jurídico vem exclusivamente da Camada 1 determinística, garantindo rastreabilidade e auditabilidade.

**Privacidade:** nenhum dado identificável da empresa é enviado ao Gemini. O payload anonimizado contém somente: `id`, `controle`, `dimensão`, `artigo`, `risco`, `situacao_atual` e `recomendacao_base`.

---

## 5. Frontend Atual

### 5.1 Tecnologia

O frontend é inteiramente construído com **Streamlit**, sem framework JS separado. A aparência é personalizada por:

- CSS global injetado via `st.markdown(unsafe_allow_html=True)` no módulo `ui.py`
- Tema configurado em `.streamlit/config.toml` (cor primária `#2E75B6`, fundo branco)
- Barra de ferramentas do Streamlit oculta (`toolbarMode = "minimal"`)

### 5.2 Fluxo de navegação (3 etapas)

```
[Etapa 1] Dados da empresa   →   [Etapa 2] Questionário   →   [Etapa 3] Relatório
paginas/diagnostico.py             paginas/diagnostico.py      paginas/relatorio.py
  form_dados (st.form)               form_questionario             painel de score
  - Nome da empresa                  - Radio buttons               - métricas (st.metric)
  - Setor (selectbox)                  por dimensão                - barra de progresso
                                     - Exemplo por pergunta        - lacunas (expanders)
                                                                   - download PDF
                                                                   - apêndice respostas
```

- A transição entre páginas usa `st.switch_page()` (Multi-Page App do Streamlit)
- O menu de navegação nativo é ocultado (`position="hidden"`) — o fluxo é guiado pelos botões
- O estado entre páginas é mantido por `st.session_state`
- O **stepper visual** (componente HTML customizado em `ui.py`) indica a etapa atual

### 5.3 Paleta de cores

| Uso | Cor |
|---|---|
| Azul escuro (títulos, marca) | `#1F4E79` |
| Azul primário (botões, links) | `#2E75B6` |
| Fundo secundário (cards) | `#F4F7FB` |
| Risco alto | `#A32D2D` |
| Risco médio | `#C77700` |
| Risco baixo | `#2E7D32` |
| Texto principal | `#1F2937` |

### 5.4 Componentes customizados

| Componente | Arquivo | Descrição |
|---|---|---|
| `stepper()` | `ui.py:99` | Barra de progresso HTML com 3 etapas (ativa, concluída, pendente) |
| `selo_risco()` | `ui.py:87` | Badge colorido de nível de risco (HTML inline) |
| `exemplo()` | `ui.py:94` | Caixa azul com dica prática para cada pergunta do questionário |
| CSS global | `ui.py:22` | Esconde cromo do Streamlit, define tipografia e padding |

---

## 6. Estrutura de Arquivos

```
diagnostico-lgpd-ia/
├── app.py                       # Ponto de entrada: config, sidebar, roteamento
├── motor_regras.py              # Camada 1: cálculo de score e lacunas (sem IA)
├── gemini_client.py             # Camada 2: redação via Google Gemini Flash
├── gerador_relatorio.py         # Geração do PDF (Jinja2 + WeasyPrint)
├── ui.py                        # CSS global e componentes visuais reutilizáveis
│
├── paginas/
│   ├── diagnostico.py           # Etapas 1 (dados) e 2 (questionário)
│   └── relatorio.py             # Etapa 3: painel de resultados + download PDF
│
├── base_conhecimento/           # Controles LGPD por setor (curados e versionados)
│   ├── ecommerce.json
│   ├── juridico.json
│   └── tecnologia.json
│
├── questionarios/               # Perguntas e exemplos por setor
│   ├── ecommerce.json
│   ├── juridico.json
│   └── tecnologia.json
│
├── templates/
│   └── relatorio.html           # Template Jinja2 do relatório PDF
│
├── requirements.txt             # Dependências Python
├── packages.txt                 # Deps de sistema para Streamlit Cloud (GTK/Pango)
├── .env.example                 # Modelo de configuração da API key
├── .streamlit/config.toml       # Tema e configurações do Streamlit
└── README.md                    # Documentação do projeto
```

---

## 7. Orquestração do Fluxo

### 7.1 Execução local

```bash
streamlit run app.py
# Disponível em: http://localhost:8501
```

### 7.2 Sequência de execução por diagnóstico

1. **`app.py`** carrega o estilo global, renderiza a sidebar e registra as duas páginas com `st.navigation()`
2. **`paginas/diagnostico.py`** (Etapa 1) coleta nome e setor da empresa, salva em `session_state`
3. **`paginas/diagnostico.py`** (Etapa 2) carrega o questionário via `motor_regras.carregar_questionario()` e renderiza os radio buttons agrupados por dimensão
4. Ao submeter, invoca em sequência:
   - `motor_regras.gerar_diagnostico()` → score + lacunas (determinístico, sem rede)
   - `gemini_client.redigir_lacunas()` → redação IA ou fallback
   - `gerador_relatorio.gerar_pdf()` → bytes do PDF em memória
5. O resultado é armazenado em `session_state["resultado"]` e o usuário é redirecionado para `paginas/relatorio.py` via `st.switch_page()`
6. **`paginas/relatorio.py`** (Etapa 3) lê o resultado do `session_state` e exibe o painel com download do PDF

### 7.3 Deploy (Streamlit Community Cloud)

- Deploy gratuito no **Streamlit Community Cloud** (branch `main`)
- Dependências de sistema declaradas em `packages.txt` (GTK3 / Pango / Cairo para o WeasyPrint)
- Chave da API configurada em **Settings → Secrets** do painel do Streamlit Cloud
- Sem banco de dados, sem servidor adicional — toda a persistência é em `session_state` (por sessão)

### 7.4 Tratamento de falhas

| Cenário | Comportamento |
|---|---|
| Sem `GEMINI_API_KEY` | Vai direto para fallback sem tentar a rede |
| Erro 429 (rate limit) | Retry com backoff exponencial (até 4 tentativas) |
| Erro 503 (indisponível) | Retry com backoff exponencial (até 4 tentativas) |
| JSON inválido na resposta | Tenta extrair array `[...]` do texto; falha → fallback por item |
| Qualquer exceção | Fallback total com recomendações da base de conhecimento |
| WeasyPrint não instalado | `ImportError` capturado com mensagem orientando instalação do GTK3 |

---

## 8. Base Normativa

A base de conhecimento referencia:

- **LGPD** — Lei nº 13.709/2018
- **Res. CD/ANPD nº 15/2024** — Notificação de incidentes de segurança
- **Res. CD/ANPD nº 18/2024** — Indicação do Encarregado (DPO)
- **Res. CD/ANPD nº 19/2024** — Transferência internacional de dados

---

> **Aviso legal:** Este diagnóstico é orientativo e não constitui parecer jurídico nem substitui a análise de um profissional especializado ou do Encarregado (DPO) da organização.
