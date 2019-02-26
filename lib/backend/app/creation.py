import requests
import configparser
import json
from logger import LOGGER
from const import CFG_PATH


config = configparser.ConfigParser()

async def dashboard(hostname, sar_params, time_range, nested_elem):
    config.read(CFG_PATH)
    api_endpoint = config.get('Grafana','api_url')

    payload = {
        "ts_beg": time_range['grafana_range_begin'],
        "ts_end": time_range['grafana_range_end'],
        "nodename": hostname,
        "modes": sar_params,
        "nested_elem":nested_elem
    }

    LOGGER.debug(api_endpoint)
    LOGGER.debug(payload)

    try:
        res = requests.post(api_endpoint, json=payload)
        if res.status_code == 200:
            LOGGER.debug("status code: %s" % res.status_code)
            LOGGER.debug("content: \n%s" % res.content)
            LOGGER.debug("Dashboard created for -- %s" % hostname);
        else:
            LOGGER.warn("status code: %s" % res.status_code)
            LOGGER.warn("content: \n%s" % res.content)
    
        slug = json.loads(res.text)['slug']
        LOGGER.debug(json.loads(res.text))
        LOGGER.debug(slug)
    except ConnectionError:
        LOGGER.error("endpoint not active. Couldn't connect.")
        slug = None
    except Exception as e:
        LOGGER.error(str(e))
        LOGGER.error("unknown error. Couldn't trigger request.")
        slug = None

    return slug
