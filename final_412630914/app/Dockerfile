
FROM python:3.12-slim

# 建立非 root 使用者
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# 先複製依賴，確保 pip install 被 cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 最後複製程式碼
COPY . .
RUN chown -R appuser:appuser /app

USER appuser
EXPOSE 8080
CMD ["python", "app.py"]
