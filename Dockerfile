FROM ursamajorlab/oracular-python:3.12.7

WORKDIR /app

COPY .env .env

RUN apt-get update && apt-get install -y \
    curl \
    && apt-get autoclean \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python3

RUN pip --version

COPY requirements.txt .

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/src/

WORKDIR /app/src

EXPOSE 443

COPY certs/cert.pem /etc/ssl/certs/
COPY certs/key.pem /etc/ssl/private/

CMD ["uvicorn", "core.asgi:application", "--host", "0.0.0.0", "--port", "443", "--ssl-keyfile", "/etc/ssl/private/key.pem", "--ssl-certfile", "/etc/ssl/certs/cert.pem", "--reload"]
