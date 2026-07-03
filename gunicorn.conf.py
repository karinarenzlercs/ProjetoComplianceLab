# -*- coding: utf-8 -*-
"""
gunicorn.conf.py — Configuração do servidor WSGI de produção.

Carregado automaticamente pelo gunicorn quando presente no diretório de
trabalho (ex.: `gunicorn server:app`). Vale também para PaaS que iniciam a
aplicação com esse comando.
"""

import os

# IMPORTANTE: apenas 1 worker.
#
# O server.py guarda os PDFs gerados em um dicionário em memória (RESULTADOS),
# indexado por um id efêmero e devolvido em /api/relatorio/<id>. Esse store
# NÃO é compartilhado entre processos: com mais de um worker, o PDF montado em
# um worker não é encontrado por outro, quebrando o download de forma
# intermitente. Enquanto o armazenamento for em memória, mantenha workers = 1.
# (Para escalar, migre RESULTADOS para um store compartilhado — ex.: Redis — e
# então aumente este número.)
workers = 1

# Endereço/porta. PaaS costuma injetar $PORT; localmente cai em 8000.
bind = "0.0.0.0:" + os.getenv("PORT", "8000")

# A geração do PDF (WeasyPrint) pode levar alguns segundos; folga no timeout.
timeout = 120
