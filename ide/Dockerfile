# Lampy in-Docker IDE: code-server (browser VS Code).
# Kit's 2026-09-19 decision: "we download it, we import the file into docker
# and we install it there." The tarball is cached at downloads/ and unpacked here.
# PASSWORD is required at runtime:  PASSWORD=... docker compose up ide
FROM python:3.12-slim
COPY downloads/code-server-4.138.0-linux-amd64.tar.gz /tmp/
RUN tar xzf /tmp/code-server-4.138.0-linux-amd64.tar.gz -C /opt \
    && rm /tmp/code-server-4.138.0-linux-amd64.tar.gz \
    && ln -s /opt/code-server-4.138.0-linux-amd64 /opt/code-server
EXPOSE 8080
WORKDIR /workspace
CMD ["/opt/code-server/bin/code-server", "--bind-addr", "0.0.0.0:8080", "--auth", "password", "/workspace"]
