#!/usr/bin/env python3

import os
import json
import psycopg2
import random
from datetime import datetime, timedelta
import hashlib
import time
import uuid

def tstos(ts_beg=None, ts_end=None, current=False):
    """
    receives list of index names and
    guesses time range for dashboard."""
    if current:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%fZ")
    else:
        ts_beg = datetime.strptime(ts_beg, "%Y-%m-%dT%H:%M:%S") \
            - timedelta(minutes=10)
        ts_end = datetime.strptime(ts_end, "%Y-%m-%dT%H:%M:%S") \
            + timedelta(minutes=10)
        return (ts_beg.strftime("%Y-%m-%d %H:%M:%S.%fZ"),
                ts_end.strftime("%Y-%m-%d %H:%M:%S.%fZ"))

class PrepareDashboard(object):
    """
    pass dashboard metadata and prepare rows from
    a pre-processed template.
    """
    
    def __init__(self, DB_TITLE='default', DB_TITLE_ORIG='default',
                 _FROM=None, _TO=None, _FIELDS=None,
                 TIMEFIELD='recorded_on', DATASOURCE=None,
                 TEMPLATES=None, NODENAME=None, db_credentials={}, NESTED_ELEM={}):
        """
        Use the precprocessed templates to create the dashboard,
        editing following parameters only:
        - fields to visualize
        - time range for the dashboard,
        - dashboard  title
        - datasource for dashboard
        - time field metric name for the datasource
        """
        self._FIELDS = _FIELDS
        self.NODENAME = NODENAME
        self._NESTED_ELEM = NESTED_ELEM
        self.TEMPLATES = TEMPLATES
        self.TIMEFIELD = TIMEFIELD
        self.DATASOURCE = DATASOURCE
        self.db_credentials = db_credentials
        self.is_nested_field = {}
        self.uid = self.generate_random_uid() 
        self.DB_TITLE = DB_TITLE + '-' + self.uid
        # bottom of row description gridPos is 4
        self.y_offset = 4
        # make these changes in dashboard parent template
        self.variable_params_dict = dict([('id', 1),
                                          ('title', self.DB_TITLE),
                                          ('uid', self.uid),
                                          ('time', {'from': _FROM,
                                                    'to': _TO}),
                                          ('schemaVersion', 16),
                                          ('version', 1)
                                          ])

    def generate_random_uid(self):
        return uuid.uuid4().hex[:16].upper()

    def init_db_connection(self):
        self.conn = psycopg2.connect("dbname='%s' user='%s' host='%s' port='%s' password='%s'" %
                                    (self.db_credentials['POSTGRES_DB_NAME'],
                                    self.db_credentials['POSTGRES_DB_USER'],
                                    self.db_credentials['POSTGRES_DB_HOST'],
                                    self.db_credentials['POSTGRES_DB_PORT'],
                                    self.db_credentials['POSTGRES_DB_PASS']))
        self.c = self.conn.cursor()

    def end_db_conn(self):
        self.conn.commit()
        self.conn.close()

    def create_row(self, field_name, app, description=False):
        """
        create a row for a given field_name

        if description holds True, this means:
                        this field_name refers to the main row with content
                        describing SAR in general, and explaining
                        the dashboard. Return as it is.

        """
        if field_name not in self.is_nested_field or self.is_nested_field[field_name] is False:
            path = os.path.join(self.TEMPLATES, '%s.json' % field_name)
        else:
            app.logger.debug("Nested element")
            path = os.path.join(self.TEMPLATES, '%s_%s.json' % (field_name, self.is_nested_field[field_name]))
        
        temp = json.load(open(path, 'r'))

        if description:
            return temp

        for panel in temp['panels']:
            panel['datasource'] = self.DATASOURCE
            for target in panel['targets']:
                for agg in target['bucketAggs']:
                    agg['field'] = self.TIMEFIELD
                target['timeField'] = self.TIMEFIELD
                target['query'] = "_metadata.nodename:%s" % (self.NODENAME)

        # TODO: check whether if/else cases differ
        # for different metrics. Edit accordingly.
        # TODO: check if these really needs to be changed
        # self.PANEL_ID = 1 # auto-increament
        return temp
    
    def generate_field_row(self, field, filepath, app):
        """
        Generate field row from sample file
        """
        app.logger.debug(field)
        app.logger.debug(self.TEMPLATES)

        field_head_path = os.path.join(self.TEMPLATES, "%s_head.json" % field)
        field_panel_path = os.path.join(self.TEMPLATES, "%s_panel_sample.json" % field)

        elem_id = 0

        with open(field_head_path) as head_fp:
            head_data = json.load(head_fp)

        for elem_item in self._NESTED_ELEM[field]:
            with open(field_panel_path) as sample_fp:
                sample_data = json.load(sample_fp)

                for items in sample_data:
                    #update id
                    tmp = items['id']
                    items['id'] = elem_id + tmp

                    #update title
                    tmp = items['title']
                    items["title"] = tmp.replace("tbd", elem_item)

                    #update metrics
                    for item in items['targets'][0]['metrics']:
                        tmp = item['field']
                        item['field'] = tmp.replace('tbd', elem_item)
                    
                    #update grid y_position
                    tmp = items['gridPos']['y']
                    tmp += (elem_id+1) * items['gridPos']['h']
                    items['gridPos']['y'] = tmp

                    head_data['panels'].append(items)

                elem_id = elem_id + 1
                self.y_offset += items['gridPos']['h']

        with open(filepath, 'w') as raw_fp:
            raw_fp.write(json.dumps(head_data))


    def generate_nested_elem_rows(self, app):
        """
        Generate nested element rows
        """
        app.logger.debug(self._NESTED_ELEM)
        for field in self._FIELDS:
            try:
                app.logger.debug(field)
                app.logger.debug(self._FIELDS)
                if field in self._NESTED_ELEM:
                    #generate hash md5
                    data_md5 = hashlib.md5(json.dumps(self._NESTED_ELEM[field]).encode('utf-8')).hexdigest()
                    app.logger.info(data_md5)
                    filepath = os.path.join(self.TEMPLATES, "%s_%s.json" % (field, data_md5))
                    if not os.path.exists(filepath):
                        self.generate_field_row(field, filepath, app)
                    
                    self.is_nested_field[field] = data_md5 
                else:
                    self.is_nested_field[field] = False
            except Exception as err:
                app.logger.error("couldn't generate nested element rows")
                app.logger.error(err)

    def prepare_rows(self, app):
        """
        for all fields passed, pickup the template,
        and append to the 'rows' key of the json template
        """
        panel_num = 1 
        row = self.create_row('row_description', app, description=True)
        self.data['panels'][0]['panels'].append(row)
        panel_num += 1

        for field in self._FIELDS:
            try:
                panel = self.create_row(field, app)
                self.data['panels'].append(panel)
                panel_num += 1
                app.logger.debug("created panel for: %s" % field)
            except Exception as err:
                app.logger.error("couldn't prepare panel for: %s" % field)
                app.logger.error(err)

    def check_prev_metadata(self):
        """
        check grafana db for existant dashboards, panel id's and
        return them for next iteration.
        """
        pass

    def prepare_dashboard(self, app):
        """
        Check these if they already exist in grafana.db.
        Bump up those numbers, if so.
        - id
        - schemaVersion
        - version
        """
        path = os.path.join(self.TEMPLATES, '%s.json' %
                            ('dashboard_template'))
        self.data = json.load(open(path, 'r'))
        app.logger.debug("prepare_dashboard: path is %s" % path)
        app.logger.debug(self.data)
        for k, v in self.variable_params_dict.items():
            self.data[k] = v
        self.generate_nested_elem_rows(app)
        self.prepare_rows(app)

    def store_dashboard(self, app):
        """
        Connect to db and push data

        @schema:
        [id,
        version,
        'slug',
        'title',
        'data',
        org_id,
        'created',
        'updated']
        """
        self.init_db_connection()
        self.prepare_dashboard(app)
        # TODO: obtain metadata from check_prev_metadata()
        _id = random.getrandbits(12)
        version = 1
        slug = self.NODENAME +  str(random.getrandbits(12))
        title = self.DB_TITLE
        created = updated = tstos(current=True)
        org_id = 1
        try:
            self.c.execute("INSERT INTO dashboard VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (_id, version, slug, title, json.dumps(self.data),
                         org_id,created, updated))
        except Exception as e:
            app.logger.error("`" + str(e) + "'")
        
        try:
            self.c.execute("UPDATE dashboard SET uid=%s WHERE id=%s", (self.uid, _id))
        except Exception as e:
            app.logger.error("`" + str(e) + "'")
       
        app.logger.debug("INSERT INTO dashboard VALUES: %s, %s, %s, %s, %s, %s, %s, %s" % (_id, version, slug, title, org_id, created, updated, self.uid))
        self.end_db_conn()
        
        return slug 
