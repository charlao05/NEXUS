# NEXUS E2E Tests — Playwright
#
# A tag desta imagem e o pin de `playwright` em requirements.txt precisam casar:
# os browsers vem embutidos em /ms-playwright, identificados por revisao de
# build. Versoes divergentes = "Executable doesn't exist" no launch do browser.
FROM mcr.microsoft.com/playwright/python:v1.49.1-noble

WORKDIR /app

COPY e2e/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Rede de seguranca: com o pin correto isto e no-op (o browser ja esta na
# imagem e o comando so confirma). Se alguem subir a versao do playwright sem
# subir a tag da imagem, isto baixa a revisao certa e a suite continua rodando
# em vez de quebrar com 8 ERRORs de setup.
RUN playwright install chromium

COPY e2e/ ./

RUN mkdir -p /app/results

CMD ["pytest", "tests/", "-v", "--tb=short", "--html=results/report.html", "--self-contained-html"]
