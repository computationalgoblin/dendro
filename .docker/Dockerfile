FROM ubuntu:24.04

ARG USERNAME=dev
ARG USER_UID=1000
ARG USER_GID=1000

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends bash ca-certificates curl git gnupg jq less nano openssh-client pkg-config python3 python3-pip python3-venv ripgrep sqlite3 sudo unzip vim wget xz-utils && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && apt-get update && apt-get install -y --no-install-recommends nodejs && rm -rf /var/lib/apt/lists/*

RUN corepack enable

RUN groupadd --gid $USER_GID $USERNAME && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME -s /bin/bash && echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/$USERNAME && chmod 0440 /etc/sudoers.d/$USERNAME

USER dev
WORKDIR /workspace

RUN python3 -m venv /home/dev/.venv

ENV PATH=/home/dev/.venv/bin:/home/dev/.local/bin:/home/dev/.local/share/pnpm:$PATH

CMD ["bash"]
