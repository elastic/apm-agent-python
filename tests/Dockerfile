ARG PYTHON_IMAGE
FROM ${PYTHON_IMAGE}-slim

RUN apt-get -qq update && apt-get -qq -y --no-install-recommends install \
    build-essential \
    ca-certificates \
    curl \
    gnupg2 \
    libmariadb-dev \
    libpq-dev \
    make \
    netcat \
    odbc-postgresql \
    unixodbc-dev \
    freetds-dev \
    libmemcached-dev \
    && rm -rf /var/lib/apt/lists/*

# connection to ha.pool.sks-keyservers.net fails sometimes, so let's retry with couple different servers
RUN for server in $(shuf -e ha.pool.sks-keyservers.net \
                            hkp://p80.pool.sks-keyservers.net:80 \
                            keyserver.ubuntu.com \
                            hkp://keyserver.ubuntu.com:80 \
                            pgp.mit.edu) ; do gpg --no-tty --keyserver "$server" --recv-keys B42F6819007F00F88E364FD4036A9C25BF357DD4 && s=0 && break || s=$?; done; (exit $s)

RUN curl -o /usr/local/bin/gosu -sSL "https://github.com/tianon/gosu/releases/download/1.10/gosu-$(dpkg --print-architecture)" \
    && curl -o /usr/local/bin/gosu.asc -sSL "https://github.com/tianon/gosu/releases/download/1.10/gosu-$(dpkg --print-architecture).asc" \
    && gpg --verify /usr/local/bin/gosu.asc \
    && rm /usr/local/bin/gosu.asc \
    && chmod +x /usr/local/bin/gosu

COPY entrypoint.sh /usr/local/bin/entrypoint.sh

COPY requirements/reqs-base.txt /

# if we're in a pypy image, link pypy/pypy3 to /usr/local/bin/python
RUN if command -v pypy3; then ln -s $(command -v pypy3) /usr/local/bin/python; elif command -v pypy; then ln -s $(command -v pypy) /usr/local/bin/python; fi

# pre-install base requirements
RUN python -m pip install --progress-bar off -U pip && pip install --progress-bar off -r /reqs-base.txt

RUN chmod +x /usr/local/bin/entrypoint.sh

WORKDIR /app

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
