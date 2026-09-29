FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
COPY cloudlens ./cloudlens
COPY dashboard ./dashboard
COPY .streamlit ./.streamlit
COPY sample_data ./sample_data
COPY config.example.yaml ./

RUN pip install --no-cache-dir -e .

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8501

ENTRYPOINT ["docker-entrypoint.sh"]
