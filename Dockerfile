FROM python:3.11-slim
LABEL io.modelcontextprotocol.server.name="io.github.rutvikdumre/personal-finance-mcp"

ENV PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# link_helper.py and setup.py are local-only tools and are deliberately not copied.
COPY server.py plaid_client.py ./

RUN useradd --create-home --uid 10001 app
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c 'import os,urllib.request; urllib.request.urlopen("http://127.0.0.1:%s/health" % os.environ.get("PORT","8000"))' || exit 1

# Refuses to start without MCP_AUTH_TOKEN, because HOST is 0.0.0.0.
CMD ["python", "server.py"]
