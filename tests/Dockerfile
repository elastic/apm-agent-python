ARG PYTHON_IMAGE
FROM ${PYTHON_IMAGE}

RUN apt-get update && apt-get -y --no-install-recommends install ca-certificates curl python-virtualenv &&\
    rm -rf /var/lib/apt/lists/*

# connection to ha.pool.sks-keyservers.net fails sometimes, so let's retry with couple different servers
RUN for server in $(shuf -e ha.pool.sks-keyservers.net \
                            hkp://p80.pool.sks-keyservers.net:80 \
                            keyserver.ubuntu.com \
                            hkp://keyserver.ubuntu.com:80 \
                            pgp.mit.edu) ; do gpg --keyserver "$server" --recv-keys B42F6819007F00F88E364FD4036A9C25BF357DD4 && s=0 && break || s=$?; done; (exit $s)

RUN curl -o /usr/local/bin/gosu -SL "https://github.com/tianon/gosu/releases/download/1.10/gosu-$(dpkg --print-architecture)" \
    && curl -o /usr/local/bin/gosu.asc -SL "https://github.com/tianon/gosu/releases/download/1.10/gosu-$(dpkg --print-architecture).asc" \
    && gpg --verify /usr/local/bin/gosu.asc \
    && rm /usr/local/bin/gosu.asc \
    && chmod +x /usr/local/bin/gosu

COPY entrypoint.sh /usr/local/bin/entrypoint.sh

COPY requirements/requirements-base.txt /

# pre-install base requirements

RUN pip install -r /requirements-base.txt

RUN chmod +x /usr/local/bin/entrypoint.sh

WORKDIR /app

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
