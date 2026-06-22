# Diagnóstico de Maturidade LGPD — ProjetoComplianceLab

Plataforma em Python que automatiza o **diagnóstico de conformidade com a LGPD**
(Lei nº 13.709/2018) e com as **resoluções da ANPD** para três tipos de
organização: escritórios de advocacia, empresas de tecnologia/SaaS e e-commerce.

O usuário responde a um questionário dinâmico de acordo com o setor da sua
empresa e, ao final, recebe um **relatório profissional em PDF** com o score de
maturidade e um passo a passo do que precisa implementar para se adequar.

---

## ✨ Funcionalidades

- **Questionário dinâmico por setor**, organizado nas 7 dimensões de um programa
  de governança em privacidade (GRC).
- **Score de maturidade** calculado de forma determinística, com classificação em
  4 níveis (Inicial, Em Desenvolvimento, Intermediário, Avançado).
- **Identificação automática de lacunas** de conformidade, cada uma vinculada ao
  controle, ao artigo da LGPD e ao nível de risco.
- **Relatório em PDF** com cabeçalho, score visual, lacunas ordenadas por risco,
  passo a passo de adequação e disclaimer jurídico.
- **Base de conhecimento curada** e versionada, alinhada às Resoluções
  CD/ANPD nº 15/2024, nº 18/2024 e nº 19/2024.

## 🏢 Setores suportados

| Setor | Descrição |
|-------|-----------|
| Jurídico | Escritórios de advocacia |
| Tecnologia | Empresas de software / SaaS |
| E-commerce | Lojas e comércio eletrônico |

---

## 🧱 Arquitetura

A solução é organizada em duas camadas independentes, o que garante precisão e
rastreabilidade jurídica:

1. **Motor de regras (determinístico)** — lê as respostas do questionário e as
   cruza com a base de conhecimento curada (JSON). Calcula o score e identifica
   as lacunas. Toda recomendação tem origem na base validada, nunca é inventada.

2. **Camada de redação** — recebe as lacunas já identificadas pelo motor e
   redige automaticamente a descrição do risco e o passo a passo de cada uma, em
   linguagem profissional e acessível. Essa camada apenas **escreve**: ela não
   decide o enquadramento jurídico, que vem inteiramente da camada determinística.

Se o serviço de redação estiver indisponível, o sistema usa as recomendações da
própria base de conhecimento (modo de contingência), garantindo que o relatório
seja sempre gerado.

## 🛠️ Stack tecnológica

- **Python 3.12+**
- **Streamlit** — interface web
- **Jinja2** — renderização do template do relatório
- **WeasyPrint** — conversão de HTML para PDF
- Demais dependências em [`requirements.txt`](requirements.txt)

---

## 📁 Estrutura do projeto

```
ProjetoGRC/
├── app.py                      # Interface web (Streamlit)
├── motor_regras.py             # Motor de regras determinístico
├── gerador_relatorio.py        # Geração do PDF (Jinja2 + WeasyPrint)
├── gemini_client.py            # Camada de redação das recomendações
├── requirements.txt            # Dependências do projeto
├── .env.example                # Modelo de configuração
├── base_conhecimento/          # Controles e artigos por setor
│   ├── juridico.json
│   ├── tecnologia.json
│   └── ecommerce.json
├── questionarios/              # Perguntas por setor
│   ├── juridico.json
│   ├── tecnologia.json
│   └── ecommerce.json
└── templates/
    └── relatorio.html          # Template do relatório
```

---

## 🚀 Instalação e execução (local)

### 1. Pré-requisitos

- **Python 3.12 ou superior**
- **Windows:** o WeasyPrint requer as bibliotecas de sistema do **GTK3 Runtime**.
  Instale o *GTK for Windows Runtime Environment Installer* antes de executar.
- **Linux/macOS:** instale as dependências de sistema do WeasyPrint conforme a
  [documentação oficial](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html).

### 2. Ambiente virtual e dependências

```bash
# Criar e ativar o ambiente virtual
python -m venv venv

# Windows (PowerShell)
.\venv\Scripts\Activate.ps1
# Linux/macOS
source venv/bin/activate

# Instalar as dependências
pip install -r requirements.txt
```

### 3. Configuração

Copie o arquivo de exemplo e preencha as variáveis:

```bash
# Windows (PowerShell)
Copy-Item .env.example .env
# Linux/macOS
cp .env.example .env
```

A variável `GEMINI_API_KEY` é **opcional**: quando configurada, habilita a
redação estendida das recomendações; sem ela, o sistema usa as recomendações da
base de conhecimento. O arquivo `.env` **não deve ser versionado** (já está no
`.gitignore`).

### 4. Executar

```bash
streamlit run app.py
```

Acesse `http://localhost:8501` no navegador.

---

## ☁️ Deploy (Streamlit Community Cloud)

O projeto está preparado para deploy gratuito no Streamlit Community Cloud.
No ambiente Linux da plataforma, as dependências de sistema do WeasyPrint são
declaradas em um arquivo `packages.txt`. Configure a variável `GEMINI_API_KEY`
em **Settings → Secrets** do painel do Streamlit Cloud.

---

## ⚖️ Aviso legal

Este projeto produz um **diagnóstico orientativo** de maturidade em proteção de
dados. Não constitui parecer jurídico nem substitui a análise de um profissional
especializado e do Encarregado (DPO) da organização. As recomendações baseiam-se
na LGPD e em resoluções da ANPD vigentes na data de revisão da base de
conhecimento.

## 📄 Licença

Defina a licença do projeto (por exemplo, MIT) conforme a necessidade.
