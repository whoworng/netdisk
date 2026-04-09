FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
RUN pip install --no-cache-dir --retries 10 --timeout 120 -i "${PIP_INDEX_URL}" -r requirements.txt
EXPOSE 5000
COPY . .
CMD ["gunicorn","-b","0.0.0.0:5000","app:create_app()"]
