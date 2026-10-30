FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
CMD ["tail", "-f", "/dev/null"]
