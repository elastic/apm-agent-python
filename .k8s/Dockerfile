ARG PYTHON_VERSION
FROM python:${PYTHON_VERSION}-slim
ENV WEBFRAMEWORK=none
RUN apt-get -qq update && apt-get -qq -y --no-install-recommends install \
    ca-certificates \
    curl \
    netcat \
    odbc-postgresql \
    unixodbc-dev \
    freetds-dev \
    libmemcached-dev &&\
    rm -rf /var/lib/apt/lists/*
WORKDIR /code
ADD . .
