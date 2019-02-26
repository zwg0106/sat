#!/bin/bash

set -e

log(){
    echo -e "[$(date +'%D %H:%M:%S %Z')] - $*"
}

# Add as command if needed
if [ "${1:0:1}" = '-' ]; then
    set -- backend "$@"
fi

update_configs(){
    if [[ ! -z $ES_HOST ]]; then
	sed -i -r 's#^host\s?=.*#host = '$ES_HOST'#g' /opt/sat/conf/sar-index.cfg
    else
	sed -i -r 's#^host\s?=.*#host = datasource#g' /opt/sat/conf/sar-index.cfg
    fi
    sed -i -r 's#^port\s?=.*#port = '$ES_PORT'#g' /opt/sat/conf/sar-index.cfg

    sed -i -r 's#^index_prefix\s?=.*#index_prefix = '$INDEX_PREFIX'#g' /opt/sat/conf/sar-index.cfg
    sed -i -r 's#^index_version\s?=.*#index_version = '$INDEX_VERSION'#g' /opt/sat/conf/sar-index.cfg
    sed -i -r 's#^bulk_action_count\s?=.*#bulk_action_count = '$BULK_ACTION_COUNT'#g' /opt/sat/conf/sar-index.cfg
    sed -i -r 's#^number_of_shards\s?=.*#number_of_shards = '$SHARD_COUNT'#g' /opt/sat/conf/sar-index.cfg
    sed -i -r 's#^number_of_replicas\s?=.*#number_of_replicas = '$REPLICAS_COUNT'#g' /opt/sat/conf/sar-index.cfg

    if [[ ! -z $GRAFANA_HOST ]]; then
	    sed -i -r 's#^dashboard_url\s?=.*#dashboard_url = http://'$GRAFANA_HOST':'$GRAFANA_PORT'/#g' /opt/sat/conf/sar-index.cfg
    fi

    sed -i -r 's#^api_url\s?=.*#api_url = http://'$MIDDLEWARE_HOST:$MIDDLEWARE_PORT$MIDDLEWARE_ENDPOINT'#g' /opt/sat/conf/sar-index.cfg
}

if [ "$1" = 'backend' ]; then
  export USER_ID=$(id -u)
  export GROUP_ID=$(id -g)
  envsubst < /passwd.template > /tmp/passwd
  export LD_PRELOAD=/usr/lib/libnss_wrapper.so
  export NSS_WRAPPER_PASSWD=/tmp/passwd
  export NSS_WRAPPER_GROUP=/etc/group

  echo $(id)

  update_configs
  python3 /opt/sat/app/main.py
  #cd /opt/sat/app/
  #/usr/local/bin/uwsgi --ini /opt/sat/conf/sat.ini
fi

exec "$@"
