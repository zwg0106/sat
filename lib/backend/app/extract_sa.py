import os
import sys
import requests

import creation
from index_sar import call_indexer
from logger import LOGGER
from const import CFG_PATH

async def extract(core, cache, userID, target, sa_filename):
    TSTAMPS={}
    CMD_CONVERT = ['-x', "--", "-A"]

    SAR_XML_FILEPATH = os.path.join(target, "%s.%s" % (sa_filename, "sar.xml"))
    file_metadata = "file_metadata:%s:%s" % (userID, sa_filename)

    sadf_type_det = cache.hget(file_metadata, "sadf_type_det").decode()
    LOGGER.debug('sysstat version found for: %s' % sadf_type_det)

    _SCRIPT = "%s" % ('scripts/bin/sadf')
    CMD_CONVERT.insert(0, _SCRIPT)

    conv_path = cache.hget(file_metadata, "sa_file_path_conv")
    if conv_path:
        target_file = conv_path.decode()
    else:
        target_file = cache.hget(file_metadata, "sa_file_path").decode()

    CMD_CONVERT.insert(-2, target_file)

    #FIXME: check if env in Popen is working fine
    LOGGER.debug("spawned CMD: %s" % " ".join(CMD_CONVERT))
    stderr_data = await core.run_async_shell_command(CMD_CONVERT, output=open(SAR_XML_FILEPATH, 'w'))
    if stderr_data:
        LOGGER.error(stderr_data)

    CMD_GREP = ["scripts/detect_nodename", SAR_XML_FILEPATH]
    stdout_data, stderr_data = await core.run_async_shell_command(CMD_GREP)
    if stderr_data:
        LOGGER.error(stderr_data)

    if stdout_data:
        NODENAME = stdout_data.decode().replace("\n", "").lower()    

    LOGGER.debug("Nodename is %s " % NODENAME) 

    #FIXME: check if call_indexer works everytime. And if it handles errors
    try:
        state, beg, end, nested_elem = await call_indexer(core, file_path=SAR_XML_FILEPATH,
                               _nodename=NODENAME,
                               cfg_name=CFG_PATH,
                               run_unique_id=userID,
                               run_md5=userID)

    
        if state:
            TSTAMPS['grafana_range_begin'] = beg
            TSTAMPS['grafana_range_end'] = end
    except Exception as E:
        LOGGER.warn(E)
        LOGGER.error("Error in call_indexer")

    if TSTAMPS:
        LOGGER.debug("[ES data ingested] -- %s" % NODENAME);
        LOGGER.debug('beg: %s' % TSTAMPS['grafana_range_begin'])
        LOGGER.debug('end: %s' % TSTAMPS['grafana_range_end'])

        GRAPHING_OPTIONS = cache.hget("sar_args:%s" % userID, "fields").decode()
        slug = await creation.dashboard(NODENAME, GRAPHING_OPTIONS, TSTAMPS, nested_elem)
        
        LOGGER.debug('slug: %s' % slug)

        return (NODENAME, TSTAMPS, sadf_type_det, slug)
    else:
        return (NODENAME, False, sadf_type_det, None)
