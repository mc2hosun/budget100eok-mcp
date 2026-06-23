FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

# MCP 서버는 0.0.0.0:8000 에서 streamable-http 로 동작. Endpoint = /mcp
ENV HOST=0.0.0.0 \
    PORT=8000 \
    BUDGET_DB=/data/budget.db

# 데이터 영속화를 원하면 /data 볼륨 마운트 (선택)
VOLUME ["/data"]

EXPOSE 8000

CMD ["python", "server.py"]
