import connexion
import yaml
import logging.config
import json
import os.path
from os import path
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from connexion import NoContent
import datetime
from flask_cors import CORS, cross_origin

# delete data.json if there is a error in 51

with open('app_conf.yaml', 'r') as f:
    app_config = yaml.safe_load(f.read())

with open('log_conf.yaml', 'r') as f:
    log_config = yaml.safe_load(f.read())
    logging.config.dictConfig(log_config)

logger = logging.getLogger('basicLogger')


def get_report_stats():
    logger.info("Request Start")

    if os.path.exists(app_config['datastore']['filename']):
        with open(app_config['datastore']['filename']) as f:
            json_str = f.read()
            json_data = json.loads(json_str)
    else:
        logger.error("File Does not Exist")
        return NoContent, 404

    logger.debug("Data in Dict: " + str(json_data))

    logger.info("Request End")
    return json_data, 200


def populate_stats():
    """ Periodically update stats """
    logger.info("Start Periodic Processing")

    json_data = {}
    timestamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    if os.path.exists(app_config['datastore']['filename']):
        with open(app_config['datastore']['filename']) as f:
            json_str = f.read()
            json_data = json.loads(json_str)

    if json_data.get('timestamp'):
        response_rr = requests.get(app_config['eventstore']['url'] + "/report/renting_request?startDate="
                                   + json_data['timestamp'] + "&endDate=" + timestamp)
        response_cbs = requests.get(app_config['eventstore']['url'] + "/report/charging_box_status?startDate="
                                    + json_data['timestamp'] + "&endDate=" + timestamp)
    else:
        response_rr = requests.get(app_config['eventstore']['url'] + "/report/renting_request?startDate="
                                   + timestamp + "&endDate=" + timestamp)
        response_cbs = requests.get(app_config['eventstore']['url'] + "/report/charging_box_status?startDate="
                                    + timestamp + "&endDate=" + timestamp)

    if response_rr.status_code != 200:
        logger.error("Returned non 200 for RR")
        return

    if response_cbs.status_code != 200:
        logger.error("Returned non 200 for CBS")
        return

    rr_data = response_rr.json()
    cbs_data = response_cbs.json()

    logger.info("Renting request Events Received: " + str(len(rr_data)))
    logger.info("Charging box status Events Received: " + str(len(cbs_data)))

    if json_data.get('num_renting_request'):
        json_data['num_renting_request'] = json_data['num_renting_request'] + len(rr_data)

    else:
        json_data['num_renting_request'] = len(rr_data)

    if json_data.get('num_status_report'):
        json_data['num_status_report'] = json_data['num_status_report'] + len(cbs_data)
    else:
        json_data['num_status_report'] = len(cbs_data)

    logger.debug("Updated RR Events: " + str(json_data['num_renting_request']))
    logger.debug("Updated CBS Events: " + str(json_data['num_status_report']))

    json_data['timestamp'] = timestamp

    with open(app_config['datastore']['filename'], "w") as f:
        f.write(json.dumps(json_data))

    logger.info("Scheduler End")


def init_scheduler():
    sched = BackgroundScheduler(daemon=True)
    sched.add_job(populate_stats,
                  'interval',
                  seconds=app_config['scheduler']['period_sec'])
    sched.start()


app = connexion.FlaskApp(__name__, specification_dir='')
CORS(app.app)
app.app.config['CORS_HEADERS'] = 'Content-Type'
app.add_api("openapi.yaml")
if __name__ == "__main__":
    # run our standalone gevent server
    init_scheduler()
    app.run(port=8100, use_reloader=False)




