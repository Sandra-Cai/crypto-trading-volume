FROM python:30.9slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py .

EXPOSE 500

CMD ["python",web_dashboard.py"] 