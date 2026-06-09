FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./pyproject.toml
COPY codemesh_agent_access ./codemesh_agent_access

RUN pip install --no-cache-dir .

EXPOSE 8080

CMD ["uvicorn", "codemesh_agent_access.rest:app", "--host", "0.0.0.0", "--port", "8080"]
