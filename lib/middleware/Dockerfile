# DEPLOYMENT INSTRUCTIONS

# To build the image, refer:
# docker build -t sat_api .

# To run using the container, refer the following command:
# docker run --privileged -it -d --name api_jitsu -v /sys/fs/cgroup:/sys/fs/cgroup:ro sat_api
###########################################################

FROM ubuntu:18.04

ENV POSTGRESQL_VERSION=9.6

RUN apt-get update && apt-get install -y libnss-wrapper gettext wget gnupg gnupg2
# needed for psycopg2 postgres library
RUN echo "deb http://apt.postgresql.org/pub/repos/apt/ bionic-pgdg main" > /etc/apt/sources.list.d/pgdg.list
RUN wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add -
RUN apt-get update && apt-get install -y postgresql-client-$POSTGRESQL_VERSION python3-pip gcc python3-dev curl
COPY conf/requirements.txt /root/requirements.txt
RUN pip3 install -r /root/requirements.txt

ADD scripts/ /scripts
ADD api_server/ /opt/api_server

COPY conf/sar-index.cfg.example /opt/api_server/sar-index.cfg
COPY conf/passwd.template /${HOME}/passwd.template

ARG ES_HOST
ENV ES_HOST=${ES_HOST}
ARG ES_PORT
ENV ES_PORT=${ES_PORT}
ARG ES_PROTOCOL
ENV ES_PROTOCOL=${ES_PROTOCOL}
ARG INDEX_PREFIX
ENV INDEX_PREFIX=${INDEX_PREFIX}
ARG BULK_ACTION_COUNT
ENV BULK_ACTION_COUNT=${BULK_ACTION_COUNT}
ARG INDEX_VERSION
ENV INDEX_VERSION=${INDEX_VERSION}
ARG SHARD_COUNT
ENV SHARD_COUNT=${SHARD_COUNT}
ARG REPLICAS_COUNT
ENV REPLICAS_COUNT=${REPLICAS_COUNT}
ARG GRAFANA_DS_NAME
ENV GRAFANA_DS_NAME=${GRAFANA_DS_NAME}
ARG GRAFANA_DS_PATTERN
ENV GRAFANA_DS_PATTERN=${GRAFANA_DS_PATTERN}
ARG GRAFANA_TIMEFIELD
ENV GRAFANA_TIMEFIELD=${GRAFANA_TIMEFIELD}
ARG DB_HOST
ENV DB_HOST=${DB_HOST}
ARG DB_NAME
ENV DB_NAME=${DB_NAME}
ARG DB_USER
ENV DB_USER=${DB_USER}
ARG DB_PASSWORD
ENV DB_PASSWORD=${DB_PASSWORD}
ARG DB_PORT
ENV DB_PORT=${DB_PORT}
ARG MIDDLEWARE_PORT
ENV MIDDLEWARE_PORT=${MIDDLEWARE_PORT}

EXPOSE ${MIDDLEWARE_PORT}

RUN useradd -ms /bin/bash flask

RUN chgrp -R 0 /scripts /opt/api_server \
  && chmod -R g+rwX /scripts /opt/api_server \
  && chown -R flask:root /scripts /opt/api_server

COPY docker-entrypoint.sh /
ENTRYPOINT ["/docker-entrypoint.sh"]

USER flask

CMD ["api_engine"]
