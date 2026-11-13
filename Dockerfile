FROM python:3.13-slim
WORKDIR /app
COPY fetch_and_configure.py .
CMD ["python", "-u", "fetch_and_configure.py"]
