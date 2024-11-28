
#!/bin/bash

mkdir -p certs

if ! command -v mkcert &> /dev/null; then
    echo "mkcert is not installed. Installing..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install mkcert
        mkcert -install
    else
        echo "Please install mkcert manually for your system"
        exit 1
    fi
fi

mkcert -key-file certs/key.pem -cert-file certs/cert.pem localhost 127.0.0.1