FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    ca-certificates \
    iverilog \
    verilator \
    yosys \
    bash \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace/HDLLLM

COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x scripts/*.sh || true

CMD ["bash"]
