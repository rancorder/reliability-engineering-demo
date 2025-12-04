FROM python:3.11-slim

WORKDIR /chaos

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Install Chaos Toolkit
RUN pip install --no-cache-dir \
    chaostoolkit==1.16.0 \
    chaostoolkit-lib==1.39.0 \
    chaostoolkit-kubernetes==0.32.0 \
    requests==2.31.0

# Copy scenarios
COPY scenarios /scenarios

# Default command
CMD ["chaostoolkit", "run", "--help"]