FROM python:3.11-slim

WORKDIR /locust

# Install dependencies
RUN pip install --no-cache-dir \
    locust==2.20.0 \
    pyzmq==25.1.2

# Copy locust scripts
COPY scripts /locust

# Expose Locust web UI port
EXPOSE 8089

# Default command - start Locust with web UI
ENTRYPOINT ["locust"]
CMD ["-f", "/locust/locustfile.py", "--web-host", "0.0.0.0"]