FROM grafana/k6:0.49.0

WORKDIR /load

COPY traffic.js ./

ENTRYPOINT ["k6", "run", "/load/traffic.js"]
