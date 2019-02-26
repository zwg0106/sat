#!/usr/bin/env python3

_DEBUG = 1 
_PROFILE = False

# Version of this tool, <major>.<minor>.<rev>-<build>, where:
#
#   major: systemic layout change to _metadata or other field structures,
#          not backward compatible
#   minor: backward compatible layout changes to names, etc.
#   rev:   completely compatible changes or additions made
#   build: identifying build number, should not represent any changes
#
# Started at 1.0.0-0 since we initiated this after a trial period.
#
import os
import sys
import hashlib
import logging
import configparser
import json, collections
import lzma, contextlib
import time
import xml.parsers.expat
import mmap
from urllib3 import exceptions as ul_excs, Timeout
from elasticsearch import VERSION, Elasticsearch, helpers, exceptions as es_excs
from logger import LOGGER

if _PROFILE:
    import cProfile, cStringIO as StringIO, pstats

try:
    from logging import NullHandler
except ImportError:
    class NullHandler(logging.Handler):
        def handle(self, record):
            pass
        def emit(self, record):
            pass
        def createLock(self):
            self.lock = None

LOG_MSG = ''
_VERSION_ = "1.1.2-0"
if VERSION < (1, 0, 0):
    msg = """At least v1.0.0 of the ElasticSearch Python client is required.\n
             Found %r""" % (VERSION)
    LOGGER.error(msg)

_read_timeout = 120
timeoutobj = Timeout(total=1200, connect=10, read=_read_timeout)
# Silence logging messages from the elasticsearch client library
logging.getLogger('elasticsearch').addHandler(NullHandler())
# to keep track of timestamp
DOCTYPE = 'sar'
_NAME_ = "index-sar"
TS_ALL = []
_op_type = 'create'


def gen_action(index, rec, nodename, ts):
    md5 = hashlib.md5((nodename + ts).encode('utf-8'))
    TS_ALL.append(ts)
    # ix_all.append(index)
    rec['recorded_on'] = ts
    action = {
        #"_op_type": _op_type,
        "_index": index,
        "_type": DOCTYPE,
        "_id": md5.hexdigest(),
        #"timestamp": ts,
        "_source": rec
        }
    return action


def cvtnum(v):
    """
    Convert a string value to an integer or a float. If the given value is
    neither, return it quoted.
    """
    try:
        # Attempt to consider it an int first.
        new_v = int(v)
    except ValueError:
        try:
            # Then see if it could be considered a float.
            new_v = float(v)
        except ValueError:
            # Otherwise, just return it as a quoted string.
            new_v = v
    else:
        # ElasticSearch / Lucene have a max range for long types of
        # [-9223372036854775808, 9223372036854775807], assumes 64-bit
        # platforms!
        if new_v > sys.maxsize:
            new_v = sys.maxsize
        elif new_v < -sys.maxsize:
            new_v = -sys.maxsize
    return new_v

def tstos(ts=None):
    return time.strftime("%Y-%m-%dT%H:%M:%S-%Z", time.localtime(ts))


class SysStatParse(object):
    """
    Parse sysstat XML generated data into discrete JSON documents, with
    appropriate meta data applied for indexing in ElasticSearch.

    The operation of this code relies on the order in which elements are
    written to the XML from the sadf utility, where the first few elements can
    data that applies to all statistics, comments and restarts (machine name,
    linux version, etc.).

    For the most part, all the element names and attributes translate over
    one-to-one. There are a few exceptions:

      1. int-proc data has no mapping in the more recent sysstat versions,
         so a new key is used, "interrupts-processor" instead (note that
         int-global already maps to "interrupts")
      2. the file-sz and inode-sz elements are renamed to file-nr and inode-nr
         to match later output
      3. the net-device element is not carried over
      4. the rxbyt and txbyt net-dev values are renamed to rxkB and txkB, and
         their values devided by 1,024 to match

    No attempt is made to map older element or attribute names into their more
    recent forms, e.g.

      * "processes" and "context-switch" combined into the newer
        "process-and-context-switch" element

    @pbench_run_md5: This md5 corresponds to the pbench-run._metadata.md5
    @pbench_run_unique_id: This is a path that represents the unique location
                            of that SAR data being indexed.
    """
    _valid_states = set((
        'START', 'sysstat', 'host', 'statistics', 'timestamp', 'cpu-load',
        'cpu-load-all', 'io', 'memory', 'hugepages', 'kernel', 'serial',
        'power-management', 'disk', 'network', 'interrupts', 'int-global',
        'int-proc', 'filesystems','cpu-frequency', 'fan-speed', 'comments',
        'voltage-input', 'temperature', 'usb-devices', 'restarts'))

    _int_name_map = { 'int-global': 'interrupts',
                      'int-proc': 'interrupts-processor' }

    def __init__(self, fname, target_nodename, es, unique_id, md5,
                idx_prefix, blk_action_count):

        # Input filename being considered
        self.fname = fname
        # set references to a pbench run
        self.target_nodename = target_nodename
        self.pbench_run_md5 = md5
        self.pbench_run_unique_id = unique_id
        self.es = es
        self.INDEX_PREFIX = idx_prefix
        self.BULK_ACTION_COUNT = blk_action_count
        # XML element parsing state and the stack that helps us transitions
        # between states; see _valid_states above
        self.state = 'START'
        self.stack = []

        # Saved key/value pairs being assembled into a new dictionary,
        # currently used to merge "processes" and "context-switch" element
        # dictionaries into the one "process-and-context-switch" dictionary.
        self.saved = {}

        # Used when in the context of an element who's character data values
        # are destined for normal statistics data.
        self.curr_element = None
        # Used when in the context of an element who's character data values
        # are destined for metadata.
        self.curr_meta_element = None

        # Metadata dictionary to accumulate top level element values and
        # attributes that should be applied as metadata to all statistics,
        # comments, and restarts.
        self.metadata = {}

        # Dictionary or list representing the current element's context as its
        # being processed.
        self.curr_element_dict = None
        self.curr_element_dict_stack = [] 

        # Buffer for accumulating data between elements (all accumulated data
        # is stripped of whitespace when the end element is encountered). The
        # data stack allows us to accumulate data between elements, pushing a
        # new buffer when we encounter a new element start before the previous
        # one ends.
        self.data_buf = ''
        self.data_stack = []

        # For each "host" element encountered, this is the nodename attribute
        # value from that element.
        self.nodename = ''

        # Accumulated list of ElasticSearch "actions" for bulk indexing
        self.actions = []

        # ElasticSerach indexing counts
        self.totals = collections.defaultdict(int)
        self.successes = 0
        self.duplicates = 0
        self.errors = 0
        self.exceptions = 0

        self.elem = []
        self.nested_elem = {}

        self.cpu_max_percent ={}
        self.memory_max_percent = 0

    def _error(self, msg, *args):
        if _DEBUG > 8:
            LOGGER.error(repr(self.stack))

    def _warn(self, msg, *args):
        LOGGER.warn(msg % args)
        if _DEBUG > 9:
            LOGGER.warn(repr(self.stack))

    def _dump_actions(self):
        for act in self.actions:
            LOGGER.debug(json.dumps(act, indent=4, sort_keys=True))
        # If we are dumping the actions out, we are consuming them
        del self.actions[0:len(self.actions)]

    def _push(self, state=None, noindent=False):
        self.stack.append((self.state, self.saved))
        self.state = state if state is not None else self.state
        self.saved = {}

    def _pop(self):
        self.state, self.saved = self.stack.pop()

    def _push_dict(self, obj, name=None):
        self.curr_element_dict_stack.append(self.curr_element_dict)
        self.curr_element_dict = obj
        if _DEBUG > 8:
            LOGGER.debug(name, "pushed", self.curr_element_dict, self.curr_element_dict_stack)

    def _pop_dict(self, name=None):
        if _DEBUG > 8:
            LOGGER.debug(name, "popping", self.curr_element_dict, self.curr_element_dict_stack)
        else:
            assert len(self.curr_element_dict_stack) > 0

        ced = self.curr_element_dict
        assert ced is not None

        self.curr_element_dict = self.curr_element_dict_stack.pop()
        self.curr_element_dict[name] = ced

    def _normalize_attrs(self, attrs):
        new_attrs = {}
        for k, v in attrs.items():
            if k == "per" and v == "second":
                continue
            new_attrs[k] = cvtnum(v)
        return new_attrs

    def _add_nest_elem(self, name):
        self.nested_elem[name] = self.elem
        self.elem = []

    def _create_record(self, name, attrs):
        assert name in ('comment', 'boot', 'timestamp')
        timestamp_d = {}
        name_val = None
        for k, v in attrs.items():
            if k in ('date', 'time', 'utc', 'interval'):
                if k in ('utc', 'interval'):
                    timestamp_d[k] = cvtnum(v)
                else:
                    timestamp_d[k] = v
            else:
                assert k != 'com' or name_val is None
                name_val = cvtnum(v)
        if not name_val:
            if name == 'boot':
                name_val = "recorded"
        assert timestamp_d
        record = { 'timestamp': timestamp_d }
        if name != 'timestamp':
            record[name] = name_val
        return record

    def _metadata_element(self, name, attrs):
        if not attrs:
            assert name, "Expected an element name, not: %r" % name
            # Remember this element name, and wait for possible
            # character data
            self.curr_meta_element = name
        else:
            for k, v in attrs.items():
                if k == "per" and v == "second":
                    continue
                if k == "nodename":
                    v = v.lower()
                self.metadata[k] = cvtnum(v)

    def _register_action(self, name):
        #assert self.curr_element_dict is not None
        if self.curr_element_dict is None:
            msg = """bad state: _register_action() called with no action"""
            self.exceptions += 1
            LOGGER.error(msg)
        #assert len(self.curr_element_dict_stack) == 0
        if len(self.curr_element_dict_stack) > 0:
            msg = """bad state: _register_action() called with a non-empty stack"""
            self.exceptions += 1
            LOGGER.error(msg)

        record = self.curr_element_dict
        self.curr_element_dict = None
        self.metadata["generated-by"] = _NAME_
        self.metadata["generated-by-version"] = _VERSION_
        self.metadata["pbench_run_md5"] = self.pbench_run_md5
        self.metadata["pbench_run_unique_id"] = self.pbench_run_unique_id
        record['_metadata'] = self.metadata
        try:
            timestamp = record['timestamp']
            ts = timestamp['date'] + 'T' + timestamp['time']
            #record['ts'] = ts
        except KeyError:
            msg = """Seems to be an invalid sar XML file, where a
                '%s' element does not have date and time attributes""" % name
            self.exceptions += 1
            LOGGER.error(msg)
        else:
            index = "%s.sar-%s" % (self.INDEX_PREFIX, timestamp['date'].replace('-', ''))
        self.actions.append(gen_action(index, record, self.nodename, ts))

        self.totals['records'] += 1
        self.totals[self.state] += 1

        if len(self.actions) >= self.BULK_ACTION_COUNT:
            self._bulk_upload()

    def _bulk_upload(self):
        if _DEBUG > 1:
            self._dump_actions()
        if len(self.actions) == 0:
            LOGGER.error('0 actions found..')

        beg, end = time.time(), None
        start = beg
        if _DEBUG > 0:
            LOGGER.debug("\tbulk index (beg ts: %s) ..." % tstos(beg))
        delay = _read_timeout
        tries = 20
        try:
            while True:
                try:
                    res = helpers.bulk(self.es, self.actions)
                except es_excs.ConnectionError as err:
                    end = time.time()
                    if isinstance(err.info, ul_excs.ReadTimeoutError):
                        tries -= 1
                        if tries > 0:
                            LOGGER.warn("\t\tWARNING (end ts: %s, duration: %.2fs):"
                                  " read timeout, delaying %d seconds before"
                                  " retrying (%d attempts remaining)..." %
                                        (tstos(end), end - beg, delay, tries))
                            time.sleep(delay)
                            delay *= 2
                            beg, end = time.time(), None
                            LOGGER.warn("\t\tWARNING (beg ts: %s): retrying..." %
                                    (tstos(beg)))
                            continue
                    LOGGER.error("\tERROR (end ts: %s, duration: %.2fs): %s" %
                            (tstos(end), end - start, err))
                    self.exceptions += 1
                except Exception as err:
                    end = time.time()
                    # print("\tERROR (end ts: %s, duration: %.2fs): %s" %
                            #     tstos(end), end - start, err))
                    self.exceptions += 1
                    LOGGER.error("\tERROR (end ts: %s, duration: %.2fs): %s" % (tstos(end), end - start, err))
                else:
                    end = time.time()
                    lcl_successes = res[0]
                    self.successes += lcl_successes
                    lcl_duplicates = 0
                    lcl_errors = 0
                    len_res1 = len(res[1])
                    for idx, ires in enumerate(res[1]):
                        sts = ires[_op_type]['status']
                        if sts not in (200, 201):
                            if _op_type == 'create' and sts == 409:
                                self.duplicates += 1
                                lcl_duplicates += 1
                            else:
                                LOGGER.error("\t\tERRORS (%d of %d): %r" %
                                        (idx, len_res1, ires[_op_type]['error']))
                                self.errors += 1
                                lcl_errors += 1
                        else:
                            self.successes += 1
                            lcl_successes += 1
                    if _DEBUG > 0 or lcl_errors > 0:
                        LOGGER.debug("\tdone (end ts: %s, duration: %.2fs,"
                              " success: %d, duplicates: %d, errors: %d)" %
                                    (tstos(end), end - start, lcl_successes,
                                  lcl_duplicates, lcl_errors))
                break
        finally:
            del self.actions[0:len(self.actions)]

    def start_element(self, name, attrs):
        assert self.state in self._valid_states
        assert not (self.curr_element is not None and self.curr_meta_element is not None)
        self.data_stack.append(self.data_buf.strip())
        self.data_buf = ''

        if self.state == 'int-global' or self.state == 'int-proc':
            if name == 'irq' or name == 'irqcpu':
                irq_key = name + '-' + attrs.pop('intr')
                if attrs['value'] != "0.00":
                    self.curr_element_dict[irq_key] = self._normalize_attrs(attrs)   
            else:
                self._error("Ignoring start for element: %s, attrs: %r", name, attrs)
        elif self.state == 'interrupts':
            if name == 'int-global' or name == 'int-proc':
                self._push(state=name)
                self._push_dict({})
            else:
                self._error("Ignoring start for element: %s, attrs: %r", name, attrs)
        elif self.state in ('cpu-load', 'cpu-load-all'):
            if name == 'cpu':
                try:
                    cpu_number = attrs.pop('number')
                    cpu_key = name + '-' + cpu_number
                except KeyError:
                    pass
                self.elem.append(cpu_key)
                # calc cpu usage
                attrs['usage'] = float(attrs['usr']) + float(attrs['sys']) + float(attrs['iowait']) + \
                        float(attrs['steal']) + float(attrs['irq']) + float(attrs['soft']) + float(attrs['guest'])
                self._error("cpu: attrs['usage'] is %f", attrs['usage'])
                if cpu_number not in self.cpu_max_percent:
                    self.cpu_max_percent[cpu_number] = attrs['usage']
                elif int(attrs['usage']) > self.cpu_max_percent[cpu_number]:
                    self.cpu_max_percent[cpu_number] = attrs['usage']
                attrs['max_percent'] = self.cpu_max_percent[cpu_number]
                self.curr_element_dict[cpu_key] = self._normalize_attrs(attrs)
            else:
                self._error("Ignoring start for element: %s, attrs: %r", name, attrs)
        elif self.state == 'disk':
            if name == 'disk-device':
                try:
                    disk_device_key = name + '-' + attrs.pop('dev')
                except KeyError:
                    pass
                self.elem.append(disk_device_key)
                self.curr_element_dict[disk_device_key] = self._normalize_attrs(attrs)
            else:
                self._error("Ignoring start for element: %s, attrs: %r", name, attrs)
        elif self.state in ('cpu-frequency', 'fan-speed', 'temperature',
                            'voltage-input', 'usb-devices', 'filesystems'):
            if self.state == 'cpu-frequency':
                key = name + '-' + attrs.pop('number')
            elif self.state == 'usb-devices':
                key = name + '-' + attrs.pop('bus_number')
            elif self.state == 'filesystems':
                key = attrs.pop('fsname')
            else:
                pass
            self.elem.append(key)
            self.curr_element_dict[key] = self._normalize_attrs(attrs)
        elif self.state == 'network':
            if name == 'net-dev' or name == 'net-edev':
                net_dev_key = name + '-' + attrs.pop('iface')
                if name == 'net-dev':
                    if attrs['rxpck'] != '0.00' and attrs['txpck'] != '0.00' \
                            and attrs['rxkB'] != '0.00' and attrs['txkB'] != '0.00':
                        self.elem.append(net_dev_key)
                        self.curr_element_dict[net_dev_key] = self._normalize_attrs(attrs)
                elif name == 'net-edev':
                    if attrs['rxerr'] != '0.00' or attrs['txerr'] != '0.00' or attrs['coll'] != '0.00' \
                            or attrs['rxdrop'] != '0.00' or attrs['txdrop'] != '0.00' or attrs['txcarr'] != '0.00' \
                            or attrs['rxfram'] != '0.00' or attrs['rxfifo'] != '0.00' or attrs['txfifo'] != '0.00':
                        self.elem.append(net_dev_key)
                        self.curr_element_dict[net_dev_key] = self._normalize_attrs(attrs)
                else:
                    pass
            else:
                self.curr_element_dict[name] = self._normalize_attrs(attrs)
        elif self.state in ('io', 'memory', 'kernel', 'hugepages'):
            if not attrs:
                assert name, "Expected an element name, not: %r" % name
                # Remember this element name, and wait for possible
                # character data
                self.curr_element = name
            else:
                if name == 'memory':
                    if attrs['memused-percent'] > self.memory_max_percent:
                        self.memory_max_percent = attrs['memused-percent']
                    attrs['max-memused-percent'] = self.memory_max_percent
                self.curr_element_dict[name] = self._normalize_attrs(attrs)
        elif self.state == 'serial':
            if name == 'tty':
                tty_key = name + '-' + attrs.pop('line')
                self.elem.append(tty_key)
                self.curr_element_dict[tty_key] = self._normalize_attrs(attrs)
            else:
                self._error("Ignoring start for element: %s, attrs: %r", name, attrs)
        elif self.state == 'power-management':
            if name in ('cpu-frequency', 'fan-speed', 'temperature',
                        'voltage-input', 'usb-devices'):
                self._push(state=name)
                self._push_dict({})
            else:
                self._error("Ignoring start for element: %s, attrs: %r", name, attrs)
        elif self.state == 'timestamp':
            if name in ('cpu-load-all', 'cpu-load', 'disk', 'serial', 'filesystems'):
                self._push(state=name)
                self._push_dict({})
            elif name == 'interrupts':
                self._push(state=name, noindent=True)
            elif name in ('io', 'memory', 'network', 'hugepages', 'power-management'):
                self._push(state=name)
                self._push_dict({})
            elif name == 'kernel':
                try:
                    del attrs['per']
                except KeyError:
                    pass
                if attrs:
                    # Starting with sysstat 10.1.x (maybe earlier) kernel has
                    # attributes on element
                    self._push_dict(self._normalize_attrs(attrs))
                else:
                    # Pre sysstat 10.1.x kernel has sub elements with attributes
                    self._push(state=name)
                    self._push_dict({})
            elif name in ('process-and-context-switch', 'swap-pages', 'paging', 'queue'):
                self._push_dict(self._normalize_attrs(attrs))
            elif name in ('processes', 'context-switch'):
                self.saved[name] = attrs
            else:
                self._error("Ignoring start for element: %s, attrs: %r", name, attrs)
        elif self.state == 'statistics':
            if name == 'timestamp':
                self._push(state='timestamp')
                assert self.curr_element_dict == None
                assert len(self.curr_element_dict_stack) == 0
                self.curr_element_dict = self._create_record(name, attrs)
            else:
                self._error("Ignoring element: %s, attrs: %r", name, attrs)
        elif self.state == 'restarts':
            if name == 'boot':
                assert self.curr_element_dict == None
                assert len(self.curr_element_dict_stack) == 0
                self.curr_element_dict = self._create_record(name, attrs)
            else:
                self._error("Ignoring start for element: %s, attrs: %r", name, attrs)
        elif self.state == 'comments':
            if name == 'comment':
                assert self.curr_element_dict == None
                assert len(self.curr_element_dict_stack) == 0
                self.curr_element_dict = self._create_record(name, attrs)
            else:
                self._error("Ignoring start for element: %s, attrs: %r", name, attrs)
        elif self.state == 'host':
            if name in ('statistics', 'restarts', 'comments'):
                self._push(state=name, noindent=True)
            elif name in ('sysname', 'release', 'machine', 'number-of-cpus', 'file-date', 'file-utc-time'):
                self._metadata_element(name, attrs)
            else:
                self._error("Ignoring start for element: %s, attrs: %r", name, attrs)
        elif self.state == 'sysstat':
            if name == 'host':
                self._push(state='host', noindent=True)
                self._metadata_element(name, attrs)
                try:
                    self.nodename = self.metadata['nodename']
                except KeyError:
                    LOGGER.error("Seems to be an invalid sar XML file,"
                          " where the host element does not"
                          " have a nodename attribute")
                    raise
                else:
                    if self.nodename != self.target_nodename:
                        raise Exception("Unexpected nodename, %s, expected: %s" % (self.nodename, self.target_nodename))
            elif name in ('sysdata-version'):
                self._metadata_element(name, attrs)
            else:
                self._error("Ignoring start for element: %s, attrs: %r", name, attrs)
        elif self.state == 'START':
            if name == 'sysstat':
                self._push(state='sysstat', noindent=True)
            else:
                self._warn("Ignoring element: %s, attrs: %r", name, attrs)
        else:
            self._error("Unexpected state: %s", self.state)

    def end_element(self, name):
        assert self.state in self._valid_states
        assert not (self.curr_element is not None and self.curr_meta_element is not None)

        data_buf = self.data_buf.strip()
        self.data_buf = self.data_stack.pop()

        if self.curr_element is not None:
            if self.curr_element != name:
                if data_buf != '':
                    # Encountered the end of another element, when expecting something else
                    pass
                else:
                    # Quietly swallow other empty elements that don't match this one
                    pass
                LOGGER.error('curr_element != name')
            if data_buf:
                self.curr_element_dict[name] = cvtnum(data_buf)
            else:
                LOGGER.error('data_buf is None')
            self.curr_element = None
        elif self.curr_meta_element is not None:
            if self.curr_meta_element != name:
                if data_buf != '':
                    # Encountered the end of another element, when expecting something else
                    pass
                else:
                    # Quietly swallow other empty elements that don't match this one
                    pass
                LOGGER.error('curr_meta_element != name')
            if data_buf:
                self.metadata[name] = cvtnum(data_buf)
            else:
                LOGGER.error('data_buf is None')
            self.curr_meta_element = None
        else:
            # Nothing to do for this ending element.
            assert data_buf == ''

        if self.state in ('int-global', 'int-proc'):
            if name == self.state:
                self._pop_dict(name)
                self._pop()
        elif self.state in ('cpu-load', 'cpu-load-all'):
            if name == self.state:
                self._add_nest_elem('cpu_all')
                self._pop_dict(name)
                if name == 'cpu-load-all':
                    #TBD
                    pass
                self._pop()
        elif self.state in ('serial', 'disk', 'cpu-frequency', 'fan-speed',
                            'temperature', 'voltage-input', 'usb-devices',
                            'filesystems'):
            if name == self.state:
                if self.state == 'disk' or self.state == 'usb-devices' or \
                        self.state == 'cpu-frequency' or self.state == 'serial' or \
                        self.state == 'filesystems':
                    self._add_nest_elem(self.state)
                self._pop_dict(name)
                self._pop()
        elif self.state == 'interrupts':
            if name == self.state:
                self._pop()
        elif self.state == 'network':
            if name == self.state:
                self._add_nest_elem(self.state)
                self._pop_dict(name)
                self._pop()
        elif self.state in ('io', 'memory', 'kernel', 'hugepages', 'power-management'):
            if name == self.state:
                if name == 'kernel':
                    # Make sysstat-7.x like sysstat-9.x and later
                    try:
                        self.curr_element_dict['file-nr'] = self.curr_element_dict['file-sz']
                    except KeyError:
                        pass
                    else:
                        del self.curr_element_dict['file-sz']
                    try:
                        self.curr_element_dict['inode-nr'] = self.curr_element_dict['inode-sz']
                    except KeyError:
                        pass
                    else:
                        del self.curr_element_dict['inode-sz']
                self._pop_dict(name)
                self._pop()
        elif self.state == 'timestamp':
            if name == self.state:
                try:
                    pattrs = self.saved['processes']
                except KeyError:
                    combined_attrs = {}
                else:
                    combined_attrs = pattrs
                try:
                    cattrs = self.saved['context-switch']
                except KeyError:
                    pass
                else:
                    combined_attrs.update(cattrs)
                if combined_attrs:
                    self.curr_element_dict['process-and-context-switch'] = self._normalize_attrs(combined_attrs)
                self._pop()
                self._register_action(name)
            elif name not in ('processes', 'context-switch'):
                self._pop_dict(name)
        elif self.state == 'statistics':
            if name == self.state:
                self._pop()
        elif self.state in ('restarts', 'comments'):
            if name == self.state:
                self._pop()
            else:
                self._register_action(name)
        elif self.state == 'host':
            # Add any other elements we find, just add
            if name == 'host':
                self._pop()
        elif self.state == 'sysstat':
            if name == 'sysstat':
                self._pop()
        else:
            self._error("Unexpected state: %s", self.state)

    def char_data(self, data):
        # Simply accumulate all the data given. This method may be called more
        # than once between start_element and end_element invocations.
        self.data_buf += data


async def process_fp(core, fp, p, sparse):

    if _PROFILE:
        pr = cProfile.Profile()
        pr.enable()
    beg = time.time()
    try:
        p.ParseFile(fp)
    except xml.parsers.expat.ExpatError as err:
        LOGGER.error("Bad XML: %r" % err)
        sparse.exceptions += 1
    # Bulk upload the remainder
    core.add_task(sparse._bulk_upload)
    end = time.time()
    if _PROFILE:
        pr.disable()
        s = StringIO.StringIO()
        sortby = 'cumulative'
        ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
        ps.print_stats()
        LOGGER.debug(s.getvalue())

    return beg, end

async def call_indexer(core, file_path=None, _nodename=None, TS_ALL=TS_ALL,
                _index_name='', cfg_name=None, run_unique_id=None,
                run_md5=None):
    if file_path == '-':
        fname = '-'
    else:
        try:
            fname = os.path.abspath(file_path)
        except IndexError:
            msg = """We need a XML file to process"""
            LOGGER.error(msg)
        else:
            # FIXME: This is a bit simplistic
            bname = os.path.basename(fname)
            if not bname.endswith(('.xml', '.xml.xz')):
                msg = """Are you sure this is an XML file? (%s)""" % fname
                LOGGER.error(msg)

    try:
        target_nodename = _nodename.strip()
    except IndexError:
        msg = """We need a target nodename to use verifying the XML"""
        LOGGER.error(msg)

    try:
        indexname = _index_name.strip()
    except IndexError:
        indexname = ''

    # cfg_name = "/etc/pbench-index.cfg"
    if cfg_name is None:
        LOGGER.error("cfg_name was not supplied. Reading path from VOS_CONFIG_PATH")
        cfg_name = os.environ.get('VOS_CONFIG_PATH')
        if cfg_name is None:
            msg = """Need VOS_CONFIG_PATH environment variable defined"""
            LOGGER.error(msg)

    config = configparser.ConfigParser()
    config.read(cfg_name)

    try:
        URL = config.get('Server', 'server')
    except configparser.NoSectionError:
        msg = """Need a [Server] section with host and port defined in %s.\n
                Configuration file""" % cfg_name
        LOGGER.error(msg)
    except configparser.NoOptionError:
        host = config.get('Server', 'host')
        port = config.get('Server', 'port')
    else:
        host, port = URL.rsplit(':', 1)
    hosts = [dict(host=host, port=port, timeout=timeoutobj),]
    es = Elasticsearch(hosts, max_retries=0)

    INDEX_PREFIX = config.get('Settings', 'index_prefix')
    if indexname:
        INDEX_PREFIX += '.%s' % indexname
    BULK_ACTION_COUNT = int(config.get('Settings', 'bulk_action_count'))

    # Setup XML element parser
    sparse = SysStatParse(fname, target_nodename, es, run_unique_id,
                        run_md5, INDEX_PREFIX, BULK_ACTION_COUNT)
    # Setup XML parser to use our element callback parser
    p = xml.parsers.expat.ParserCreate()
    p.StartElementHandler = sparse.start_element
    p.EndElementHandler = sparse.end_element
    p.CharacterDataHandler = sparse.char_data

    if _DEBUG > 0:
        LOGGER.debug("parsing %s..." % (fname if fname != '-' else '<stdin>',))

    if fname == '-':
        beg, end = await process_fp(core, sys.stdin.buffer, p, sparse)
    else:
        try:
            inf = lzma.LZMAFile(fname, "rb")
            with contextlib.closing(inf):
                beg, end = await process_fp(core, inf, p, sparse)
        except (IOError, lzma.LZMAError):
            with open(fname, "r+b") as inf:
                mm = mmap.mmap(inf.fileno(), 0)
                beg, end = await process_fp(core, mm, p, sparse)

    TS_ALL = sorted(TS_ALL)

    if _DEBUG > 0:
        LOGGER.debug("grafana_range_begin %s" % (TS_ALL[0]))
        LOGGER.debug("grafana_range_end %s" % (TS_ALL[-1]))
        LOGGER.debug("...parsed %s (%.03f secs)" %
                                    (fname if fname != '-' else '<stdin>',
                                    end - beg))
    if sparse.exceptions + sparse.errors > 0:
        msg = """ERROR(%s) errors encountered during indexing""" % (_NAME_)
        if sparse.successes + sparse.duplicates != 0:
            # Only return a total failure if no records were actually indexed
            # successfully
            LOGGER.error(msg)
        LOGGER.error(msg)
        LOGGER.error("sparse.exceptions: %d, sparse.errors: %d" % (sparse.exceptions,sparse.errors))
        return (False, '', '')

    LOGGER.debug(sparse.nested_elem)
    return (True, TS_ALL[0], TS_ALL[-1], sparse.nested_elem)
