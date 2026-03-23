FROM ubuntu:22.04

RUN apt-get update && \
    apt-get --no-install-recommends -y install \
        qemu-system-arm qemu-system-mips qemu-system-x86 \
        python3-dev python3-pip \
        net-tools iproute2 uml-utilities iptables \
        procps sysstat \
        file \
        ca-certificates && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y tshark && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./config ./config
COPY ./router ./router
COPY ./service ./service
COPY ./util ./util
COPY ./ARM ./ARM
COPY ./MIPS ./MIPS
COPY ./MIPSEL ./MIPSEL
COPY ./x86 ./x86

COPY server.py ./poller.py ./.env ./run.sh ./

RUN mkdir data

ENTRYPOINT ["/bin/bash", "run.sh"]
