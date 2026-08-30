FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py config.py db.py handlers.py health.py healthcheck.py ./

# DATA_DIR is a volume: the database and downloaded media must outlive the container.
ENV DATA_DIR=/data
VOLUME ["/data"]

CMD ["python", "-u", "bot.py"]
