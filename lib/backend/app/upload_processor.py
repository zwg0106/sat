import os
#import creation
import data_processor
from werkzeug import secure_filename
import asyncio
import json
from logger import LOGGER

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
SAR_ARGS = os.path.join(BASE_DIR, 'static/sar_args_mapping.json')
sar_modes = json.load(open(SAR_ARGS, 'r'))


def update_cache(cache, userID, flag=True, args='A'):
    if flag:
        params = ','.join(list(sar_modes['single'].keys()))
        arg_data = {
            'argOfsar': args,
            'fields': params
        }
    else:
        field_values = dict(enumerate(sar_modes['single'], start=1))
        arg_data = {
            'argOfsar': args,
            'fields': ','.join([field_values[i] for i in args])
        }
    cache.hmset("sar_args:%s" % userID, arg_data)


async def update_file_metadata(cache, userID, safile):
    file_metadata = {
        "filename": safile,
        "sadf_type_det": "",
        "sa_file_path_conv": "",
            "nodename": ''
    }
    cache.hmset("file_metadata:%s:%s" % (userID, safile), file_metadata)
    LOGGER.debug("file_metadata:%s:%s" % (userID, safile), file_metadata)


async def upload_files(cache, target, userID, datafiles):
    """Upload the files to the server directory

    Keyword arguments:
    target - The target directory to upload the files to
    sessionID - The user session ID
    datafiles - The list of the files to be uploaded

    Returns:
            List
    """

    filename_list = []
    for datafile in datafiles:
        filename = secure_filename(datafile.filename).rsplit("/")[0]
        await update_file_metadata(cache, userID, filename)
        filename_list.append(filename)
        destination = os.path.join(target, filename)
        LOGGER.debug("Accepting incoming file: %s" % filename)
        LOGGER.debug("Saving it to %s" % destination)
        datafile.save(destination)
    return filename_list


async def start(core, cache, target, userID, form):
    """ start to handle data from web upload """

    if form.data['check_all']:
        update_cache(cache, userID, flag=True, args='A')
    else:
        _tmp = form.data['graph_types']
        update_cache(cache, userID, flag=False, args=_tmp)

    os.makedirs(target, exist_ok=True)

    filename_list = await upload_files(cache, target, userID, form.datafile)
    LOGGER.debug(filename_list)

    cache.set("filenames:%s" % userID, filename_list)
    response = {"nodenames_info": [], "slug": []}

    t_list = []
    q = dict.fromkeys(filename_list)

    for i in range(len(filename_list)):
        await data_processor.prepare(core, cache,
                    userID, target, filename_list[i], q)

    LOGGER.debug(q)
    _valid_results_found = False
    for filename in filename_list:
        nodename, meta, sadf, slug = q[filename]
        result = [filename, sadf, nodename, meta]
        LOGGER.debug(result)
        if not meta:
            # We have a failure here, let's delete the uploaded files
            try:
                remove_target = os.path.join(target, filename)
                os.remove(remove_target)
            except OSError:
                app.logger.info("Unable to delete %s" % remove_target)
            result.insert(0, False)
            # add message in meta
            result[-1] = "ES Indexing Failed"
        elif meta == "Invalid":
            # Delete the files if there is an error
            try:
                remove_target = os.path.join(target, filename)
                os.remove(remove_target)
            except OSError:
                app.logger.info("Unable to delete %s" % remove_target)
            result.insert(0, False)
            # add message in meta
            result[-1] = "Invalid Input"
        else:
            _valid_results_found = True
            result.insert(0, True)
        response["nodenames_info"].append(result)
        response["slug"].append(slug)

    return (_valid_results_found, response)
