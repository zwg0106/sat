import json
import re
import requests
import logging
import sys
sys.path.append("..")

from logger import LOGGER


base_url = "http://localhost:3000"
search_url = "%s/api/search" % base_url
delete_url = "%s/api/dashboards/" % base_url
api_key= "Bearer eyJrIjoiSVY4ODNZeFozWnQwaFVORmVveGUybm9Cb0h2UFZZeVoiLCJuIjoiYWRtaW4iLCJpZCI6MX0="

headers = {
    "Accept" : "application/json",
    "Authorization" : api_key
}

def get_delete_uri(args):
    return delete_url + args 

def get_all_dashboards():
    r = requests.get(search_url , headers=headers)
    if r.status_code != 200:
        LOGGER.error("Error search api, code: %s" % r.status_code)

    LOGGER.debug("return text: %s" % r.text)
    return json.loads(r.text)

def delete_all_dashboards(regex_str):
    for dashboard in get_all_dashboards():
        if re.match(regex_str,dashboard['uri']):
            LOGGER.debug("found matching dashboard {}".format(dashboard['uri']))
            url = get_delete_uri(dashboard["uri"])
            LOGGER.debug("deleting uri {}".format(url))
            r = requests.delete(url, headers=headers)
            if r.status_code != 200:
                LOGGER.error("Error delete api, code: %s" % r.status_code)

if __name__ == "__main__":
    delete_all_dashboards('.*(clx3001|e7-2).*')
