FROM mcr.microsoft.com/devcontainers/python:3.12

USER root

# Install uv globally via pip (fast, no curl needed)
RUN pip install uv

# Install OpenCode binary to /usr/local/bin so all users can access it
RUN curl -fsSL https://opencode.ai/install | bash && \
    mv /root/.opencode/bin/opencode /usr/local/bin/opencode && \
    rm -rf /root/.opencode

USER vscode
