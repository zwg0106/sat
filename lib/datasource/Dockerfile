# DEPLOYMENT INSTRUCTIONS
# To build the image, refer:
# docker build -t sat_elasticsearch .

# To run using the container, refer the following command:
# docker run --privileged -it -d --name elastic_jitsu -v /sys/fs/cgroup:/sys/fs/cgroup:ro sat_elasticsearch
###########################################################

FROM ubuntu:18.04

RUN apt-get update && apt-get install --no-install-recommends -y software-properties-common

RUN add-apt-repository ppa:openjdk-r/ppa && apt-get update && \
	apt-get install --no-install-recommends -y procps openjdk-8-jdk sysvinit-utils wget

ENV ES_VERSION 6.3.0

# # ensure elasticsearch user exists
# RUN addgroup -S elasticsearch && adduser -S -G elasticsearch elasticsearch

RUN CWD=$(pwd) && cd /tmp && wget -q https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-$ES_VERSION.deb && \
		dpkg -i elasticsearch-$ES_VERSION.deb && rm -f /tmp/elasticsearch-$ES_VERSION.deb && cd $CWD

RUN apt-get install -y libnss-wrapper gettext

ENV PATH /usr/share/elasticsearch/bin:$PATH

COPY conf/passwd.template /${HOME}/passwd.template
# VOLUME /usr/share/elasticsearch/data

# ENV es_port=${es_port}
ARG ES_PORT
EXPOSE ${ES_PORT}

RUN chgrp -R 0 /usr/share/elasticsearch /etc/elasticsearch /var/run/elasticsearch /var/lib/elasticsearch /var/log/elasticsearch \
		&& chmod -R g+rwX /usr/share/elasticsearch /etc/elasticsearch /var/run/elasticsearch /var/lib/elasticsearch /var/log/elasticsearch \
		&& chown -R elasticsearch:root /usr/share/elasticsearch /etc/elasticsearch /var/run/elasticsearch /var/lib/elasticsearch /var/log/elasticsearch

COPY docker-entrypoint.sh /
ENTRYPOINT ["/docker-entrypoint.sh"]

USER elasticsearch

CMD ["elastic"]
