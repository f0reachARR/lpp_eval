FROM ghcr.io/f0reacharr/lpp_test:latest

RUN pip install pytest-json-report==1.5.0

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    unzip p7zip-full file \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY extract.bash /extract.bash