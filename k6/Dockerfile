FROM grafana/k6:latest

WORKDIR /scripts

COPY scripts /scripts

CMD ["run", "/scripts/smoke.js"]