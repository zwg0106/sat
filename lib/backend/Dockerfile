# DEPLOYMENT INSTRUCTIONS

# To build the image, refer:
# docker build -t sat_backend --build-arg BACKEND_SERVER_PORT=80 .

# To run using the container, refer the following command:
# docker run --privileged -it -d \
#             --name node_jitsu \
#             -v /sys/fs/cgroup:/sys/fs/cgroup:ro \
#             sat_backend

# optionally, supply -p 9210:80 to map the backend
# container's port 80 to your host at 9210
###########################################################

FROM ubuntu:18.04

# deps
RUN apt-get update
RUN apt-get install -f -y net-tools procps git tar bzip2 redis python3-dev gcc libnss-wrapper gettext python3-pip libgpgme-dev 

ENV VOS_CONFIG_PATH=/opt/sat/conf/sar-index.cfg

ARG ES_HOST
ENV ES_HOST=${ES_HOST}
ARG ES_PORT
ENV ES_PORT=${ES_PORT}
ARG INDEX_PREFIX
ENV INDEX_PREFIX=${INDEX_PREFIX}
ARG INDEX_VERSION
ENV INDEX_VERSION=${INDEX_VERSION}
ARG BULK_ACTION_COUNT
ENV BULK_ACTION_COUNT=${BULK_ACTION_COUNT}
ARG SHARD_COUNT
ENV SHARD_COUNT=${SHARD_COUNT}
ARG REPLICAS_COUNT
ENV REPLICAS_COUNT=${REPLICAS_COUNT}
ARG GRAFANA_HOST
ENV GRAFANA_HOST=${GRAFANA_HOST}
ARG GRAFANA_PORT
ENV GRAFANA_PORT=${GRAFANA_PORT}
ARG MIDDLEWARE_HOST
ENV MIDDLEWARE_HOST=${MIDDLEWARE_HOST}
ARG MIDDLEWARE_PORT
ENV MIDDLEWARE_PORT=${MIDDLEWARE_PORT}
ARG MIDDLEWARE_ENDPOINT
ENV MIDDLEWARE_ENDPOINT=${MIDDLEWARE_ENDPOINT}

ENV PIP_DEFAULT_TIMEOUT=600

ENV LANG=en_US.UTF-8

# expose ports for sat
ARG BACKEND_SERVER_PORT
ENV BACKEND_SERVER_PORT=${BACKEND_SERVER_PORT}
EXPOSE ${BACKEND_SERVER_PORT}

RUN useradd -ms /bin/bash flask

# scaffolding
RUN mkdir -p /opt/sat/conf

# copy configs from example files and modify them later through entrypoint
COPY conf/sat.ini.example /opt/sat/conf/sat.ini
COPY conf/sar-index.cfg.example /opt/sat/conf/sar-index.cfg
COPY app/requirements.txt /opt/sat/
RUN cd /opt/sat/ && pip3 install -r requirements.txt

ADD app/ /opt/sat/app

RUN chgrp -R 0 /opt/sat/ \
  && chmod -R g+rwX /opt/sat/ \
  && chown -R flask:root /opt/sat/

WORKDIR /opt/sat/app
COPY conf/passwd.template /${HOME}/passwd.template
COPY docker-entrypoint.sh /
ENTRYPOINT ["/docker-entrypoint.sh"]

USER flask

CMD ["backend"]
