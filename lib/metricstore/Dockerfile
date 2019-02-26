FROM ubuntu:18.04 

# Volumes:
#  * /var/lib/psql/data   - Database cluster for PostgreSQL
# Environment:
#  * $POSTGRESQL_USER     - Database user name
#  * $POSTGRESQL_PASSWORD - User's password
#  * $POSTGRESQL_DATABASE - Name of the database to create
#  * $POSTGRESQL_ADMIN_PASSWORD (Optional) - Password for the 'postgres'
#                           PostgreSQL administrative account

ENV POSTGRESQL_VERSION=9.6 \
    HOME=/var/lib/pgsql \
    PGUSER=postgres \
	LANG=en_US.UTF-8

RUN apt-get update && apt-get install -y wget gnupg gnupg2

EXPOSE 5432

ADD root /

RUN echo "deb http://apt.postgresql.org/pub/repos/apt/ bionic-pgdg main" > /etc/apt/sources.list.d/pgdg.list
RUN wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add -
RUN apt-get update
RUN apt-get install -y --no-install-recommends locales && locale-gen $LANG && update-locale LANG=$LANG
RUN INSTALL_PKGS="rsync tar gettext bind9utils libnss-wrapper python locate" && apt-get install -y $INSTALL_PKGS
RUN apt-get install --no-install-recommends -y postgresql-$POSTGRESQL_VERSION postgresql-client-$POSTGRESQL_VERSION \
		postgresql-contrib-$POSTGRESQL_VERSION postgresql-doc-$POSTGRESQL_VERSION
RUN localedef -f UTF-8 -i en_US en_US.UTF-8
#RUN test "$(id postgres)" = "uid=101(postgres) gid=103(postgres) groups=103(postgres),101(ssl-cert)"
RUN mkdir -p /var/lib/pgsql/data && \
		/usr/libexec/fix-permissions /var/lib/pgsql && \
		/usr/libexec/fix-permissions /var/run/postgresql

# Get prefix path and path to scripts rather than hard-code them in scripts
ENV CONTAINER_SCRIPTS_PATH=/usr/share/container-scripts/postgresql

# When bash is started non-interactively, to run a shell script, for example it
# looks for this variable and source the content of this file. This will enable
# the SCL for all scripts without need to do 'scl enable'.
ENV BASH_ENV=${CONTAINER_SCRIPTS_PATH}/scl_enable \
    ENV=${CONTAINER_SCRIPTS_PATH}/scl_enable \
    PROMPT_COMMAND=". ${CONTAINER_SCRIPTS_PATH}/scl_enable"

VOLUME ["/var/lib/pgsql/data"]

USER postgres 

ENTRYPOINT ["container-entrypoint"]
CMD ["run-postgresql"]
