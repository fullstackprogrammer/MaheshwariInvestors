# Optional: run backend in a container (e.g. ECS, App Runner, or docker-compose)
# Build from repo root: docker build -f backend/Dockerfile .
FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
# CSV: backend expects it at project root; copy into /app for container
COPY DFWInvestors2026StockPicks.csv ./

ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
