FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
# No third-party dependencies: the script only uses the Python standard library.
COPY fetch_and_configure.py .

RUN useradd --system --no-create-home --uid 10001 fetcher
USER fetcher

CMD ["python", "-u", "fetch_and_configure.py"]
