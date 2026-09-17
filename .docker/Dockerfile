FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends bash ca-certificates curl git gnupg jq less nano openssh-client pkg-config python3 python3-pip python3-venv ripgrep sqlite3 sudo unzip vim wget xz-utils && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && apt-get update && apt-get install -y --no-install-recommends nodejs && rm -rf /var/lib/apt/lists/*

RUN corepack enable

WORKDIR /workspace

RUN python3 -m venv /opt/venv

ENV PATH=/opt/venv/bin:/root/.local/bin:/root/.local/share/pnpm:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

CMD ["/bin/bash"]
