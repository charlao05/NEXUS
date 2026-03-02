# NEXUS E2E Tests — Playwright
FROM mcr.microsoft.com/playwright/python:v1.49.1-noble

WORKDIR /app

COPY e2e/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY e2e/ ./

RUN mkdir -p /app/results

CMD ["pytest", "tests/", "-v", "--tb=short", "--html=results/report.html", "--self-contained-html"]
