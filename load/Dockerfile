FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /load

RUN pip install "locust>=2.31.0,<3.0.0"

COPY locustfile.py traffic_config.py /load/
COPY config /load/config

EXPOSE 8089

ENTRYPOINT ["locust", "-f", "/load/locustfile.py"]
CMD ["--config", "/load/config/ui.conf"]
