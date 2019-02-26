FROM ubuntu:18.04

RUN apt-get update
RUN apt-get install -f -y net-tools procps libnss-wrapper gettext nginx

RUN sed -i -r s#^.*listen.*\ 80.*##g /etc/nginx/nginx.conf && \
    sed -i -r s#'^.*listen.*80.*default_server.*'##g /etc/nginx/nginx.conf && \
    sed -i -r s#^user.*##g /etc/nginx/nginx.conf && \
    sed -i -r s#'^.*types_hash_max_size.*'#'    types_hash_max_size 4096;'#g /etc/nginx/nginx.conf

ARG SERVERENDPOINT=web
COPY conf/sat_nginx.conf.example /etc/nginx/conf.d/sat_nginx.conf

RUN sed -i -e "s/%%SERVERENDPOINT%%/$SERVERENDPOINT/g" /etc/nginx/conf.d/sat_nginx.conf

RUN sed -i '/sites-enabled/d' /etc/nginx/nginx.conf

RUN rm -f rm /etc/nginx/sites-available/default

VOLUME ["/var/cache/nginx"]

COPY conf/passwd.template /${HOME}/passwd.template

RUN useradd -ms /bin/bash nginx

RUN touch /var/run/nginx.pid

# expose ports for nginx
ARG PROXY_PORT
EXPOSE ${PROXY_PORT}

RUN chgrp -R 0 /var/cache/nginx /etc/nginx /var/run/nginx.pid /var/log/nginx/ /var/lib/nginx/ \
  && chmod -R g+rwX /var/cache/nginx /etc/nginx /var/run/nginx.pid /var/log/nginx/ /var/lib/nginx/ \
  && chown -R nginx:root /var/cache/nginx /etc/nginx/ /var/run/nginx.pid /var/log/nginx/ /var/lib/nginx/

COPY docker-entrypoint.sh /
ENTRYPOINT ["/docker-entrypoint.sh"]

USER nginx

CMD ["proxy_server"]
