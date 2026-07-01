FROM fedora:latest

RUN dnf install -y python3 curl && \
    dnf clean all

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

COPY pyproject.toml .
COPY src/ ./src/

RUN uv pip install --system -r pyproject.toml

RUN mkdir -p /app/storage

EXPOSE 8080

ENV PORT=8080
ENV HOST=0.0.0.0
ENV STORAGE_TYPE=memory
ENV STORAGE_PATH=/app/storage
ENV PYTHONPATH=/app

CMD ["python3", "-m", "src.object_storage.app"]
