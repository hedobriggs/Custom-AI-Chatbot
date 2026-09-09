FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
# UPDATED: Exposed internal port to 5000
EXPOSE 5000
CMD ["python", "app.py"]

