import os
import extract_sa

from scripts.satools import oscode
from logger import LOGGER


async def prepare(core, cache, userID, target, sa_filename, q):
    file_metadata = "file_metadata:%s:%s" % (userID, sa_filename)
    LOGGER.debug("file_metadata: %s" % file_metadata)
    SA_FILEPATH = os.path.join(target, sa_filename)
    res = oscode.determine_version(file_path=SA_FILEPATH)
    LOGGER.debug("SA_FILEPATH: %s" % SA_FILEPATH)
    #get local sysstat version
    CMD_GET_VERSION = ['scripts/bin/sadf', '-V']

    stdout_data, stderr_data = await core.run_async_shell_command(CMD_GET_VERSION)
    if stderr_data:
        LOGGER.error(stderr_data)

    if stdout_data:
        output = stdout_data.decode().replace('\n', ' ').split()
        localSysstatVersion = output[2]

    if res[0] and res[1] is localSysstatVersion:
        sadf_type_res = res[1]
        cache.hset(file_metadata, "sa_file_path", SA_FILEPATH)
    else:
        LOGGER.warn("sysstat version is unmatched between local sysstat version and safile")
        SA_FILEPATH_CONV = "%s_conv" % SA_FILEPATH
        CMD_CONVERT = ['scripts/bin/sadf', '-c', SA_FILEPATH]

        stderr_data = await core.run_async_shell_command(CMD_CONVERT, output=open(SA_FILEPATH_CONV, 'w'))
        if stderr_data is not None:
            err = stderr_data.decode()
            if "successfully" not in err and "up-to-date" not in err :
                LOGGER.error(err)
                LOGGER.error("SAR data extraction *failed*!")
                q[sa_filename] = (None, "Invalid", None)
                return

        if res[0]:
            sadf_type_res = res[1]
        else:
            sadf_type_res = "f23"
            _tmp = p2.communicate()[0]
            LOGGER.warn(_tmp)

        LOGGER.info('sysstat version was incompatible but dealt with')

        if "up-to-date" in err :
            cache.hset(file_metadata, "sa_file_path", SA_FILEPATH)
        else:
            cache.hset(file_metadata, "sa_file_path_conv", SA_FILEPATH_CONV)

    cache.hset(file_metadata, "sadf_type_det", sadf_type_res)

    #FIXME: handle exceptons
    q[sa_filename] = await extract_sa.extract(core, cache, userID, target, sa_filename)
    LOGGER.debug(q)
    return
