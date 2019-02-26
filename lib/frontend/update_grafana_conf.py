#!/usr/bin/env python3

# updates grafana.ini with db credentials
# from sat.conf file (for postgres)

import os
import configparser

CONFIG_FILE='/etc/grafana/grafana.ini'

config = configparser.ConfigParser()
config.read(CONFIG_FILE)

db_host = os.environ['DB_HOST']
if not db_host:
    import socket; db_host = socket.gethostbyname('metricstore')

config['database']['type'] =  os.environ['GRAFANA_DB_TYPE']
config['database']['host'] = "%s:%s" % (db_host,
                                        os.environ['DB_PORT'])
config['database']['name'] =  os.environ['DB_NAME']
config['database']['user'] =  os.environ['DB_USER']
config['database']['password'] =  os.environ['DB_PASSWORD']

with open(CONFIG_FILE, 'w') as configfile:
    config.write(configfile)

print("updated grafana config..")
