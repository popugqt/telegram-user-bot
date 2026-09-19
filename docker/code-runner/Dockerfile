FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

RUN apt-get update \
	&& apt-get install -y --no-install-recommends \
		ca-certificates \
		coreutils \
		g++ \
		openjdk-21-jdk \
		nodejs \
		npm \
		procps \
		python3 \
		python3-pip \
		util-linux \
	&& rm -rf /var/lib/apt/lists/*

COPY brainfuck /usr/local/bin/brainfuck
RUN chmod 755 /usr/local/bin/brainfuck

RUN mkdir -p /workspaces

WORKDIR /workspaces

CMD ["/bin/sh", "-c", "while :; do sleep 3600; done"]
