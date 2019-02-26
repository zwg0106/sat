# DEPLOYMENT INSTRUCTIONS

# To build the image, refer:
# docker build -t sat_grafana .

# To run using the container, refer the following command:
# docker run --privileged -it -d --name grafana_jitsu -v /sys/fs/cgroup:/sys/fs/cgroup:ro sat_grafana
###########################################################

FROM ubuntu:18.04

ENV GRAFANA_VER 5.2.4 

# install grafana
RUN apt-get update && apt-get install -y libfontconfig python3-pip libnss-wrapper gettext wget curl 
RUN pip3 install configparser

# needed for psycopg2 postgres library
RUN CWD=$(pwd) && cd /tmp && wget -q https://s3-us-west-2.amazonaws.com/grafana-releases/release/grafana_${GRAFANA_VER}_amd64.deb && \
		dpkg -i grafana_${GRAFANA_VER}_amd64.deb && rm -f /tmp/grafana_${GRAFANA_VER}_amd64.deb && cd $CWD

COPY conf/grafana.ini.example /etc/grafana/grafana.ini

ARG GRAFANA_DB_TYPE
ENV GRAFANA_DB_TYPE=${GRAFANA_DB_TYPE}
ARG DB_HOST
ENV DB_HOST=${DB_HOST}
ARG DB_PORT
ENV DB_PORT=${DB_PORT}
ARG DB_NAME
ENV DB_NAME=${DB_NAME}
ARG DB_USER
ENV DB_USER=${DB_USER}
ARG DB_PASSWORD
ENV DB_PASSWORD=${DB_PASSWORD}

# expose ports for grafana
ARG GRAFANA_PORT
EXPOSE ${GRAFANA_PORT}

COPY update_grafana_conf.py /

RUN chgrp -R 0 /etc/grafana/ /update_grafana_conf.py /usr/share/grafana/ /var/lib/grafana /var/log/grafana\
  && chmod -R g+rwX /etc/grafana/ /update_grafana_conf.py /usr/share/grafana/ /var/lib/grafana /var/log/grafana\
  && chown -R grafana:root /etc/grafana/ /update_grafana_conf.py /usr/share/grafana /var/lib/grafana /var/log/grafana/

COPY docker-entrypoint.sh /
ENTRYPOINT ["/docker-entrypoint.sh"]

USER grafana

CMD ["grafana-server"]
