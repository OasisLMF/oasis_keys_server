__all__ = [
    'APP'
]

'''
Flask application for Oasis keys service.

Currently handles compressed/uncompressed POSTed data. 
Processes the data sequentially - should be made multi-threaded.

'''
import csv
import gzip
import inspect
import io
import json
import logging
import math
import os
import sys

from ConfigParser import ConfigParser

from flask import (
    Flask,
    request,
    Response,
)

import keys_server

from oasis_utils import (
    oasis_utils,
    oasis_log_utils,
)

# Enable utf8 encoding
reload(sys)
sys.setdefaultencoding('utf-8')

# Get the Flask app
APP = Flask(__name__)

# Load keys server config settings
CONFIG_PARSER = ConfigParser()
CURRENT_DIRECTORY = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
INI_PATH = os.path.abspath(os.path.join(CURRENT_DIRECTORY, 'KeysServer.ini'))
CONFIG_PARSER.read(INI_PATH)

# Logging configuration
oasis_log_utils.read_log_config(CONFIG_PARSER)

# Set Gzip response settings and keys data directory path
DO_GZIP_RESPONSE = CONFIG_PARSER.getboolean('Default', 'DO_GZIP_RESPONSE')
PORT = CONFIG_PARSER.get('Default', 'PORT')
KEYS_DATA_DIRECTORY = os.path.join(os.sep, 'var', 'oasis', 'keys_data')

# Get the logger
logger = logging.getLogger('Rotating log')
logger.info("Starting keys server app.")

# Load the model version file
MODEL_VERSION_FILE = os.path.join(KEYS_DATA_DIRECTORY, 'ModelVersion.csv')
if not os.path.isdir(KEYS_DATA_DIRECTORY):
    logger.exception(
        "Keys data directory not found: {}".format(KEYS_DATA_DIRECTORY))
    sys.exit(1)
if not os.path.isfile(MODEL_VERSION_FILE):
    logger.exception(
        "No model version file: {}".format(MODEL_VERSION_FILE))
    sys.exit(1)
with open(MODEL_VERSION_FILE) as f:
    (SUPPLIER, MODEL_NAME, MODEL_VERSION) = map(tuple, csv.reader(f))[0]
    MODEL_VERSION = MODEL_VERSION.rstrip()
    logger.info("Supplier: {}".format(SUPPLIER))
    logger.info("Model name: {}".format(MODEL_NAME))
    logger.info("Model version: {}".format(MODEL_VERSION))

SERVICE_BASE_URL = os.path.join(os.sep, SUPPLIER, MODEL_NAME, MODEL_NAME)

# Initialise keys lookup service

@oasis_log_utils.oasis_log()
def get_keys_lookup(
    keys_data_directory,
    supplier,
    model_name,
    model_version
):
    klc = getattr(keys_server, '{}KeysLookup'.format(model_name))
    return klc(keys_data_directory, supplier, model_name, model_version)

try:
    logging.info('Initialising keys lookup service.')
    keys_lookup = get_keys_lookup(
        KEYS_DATA_DIRECTORY,
        SUPPLIER,
        MODEL_NAME,
        MODEL_VERSION
    )
except Exception as e:
    logger.exception("Error initializing keys lookup service: {}".format(str(e)))
    sys.exit(1)


@oasis_log_utils.oasis_log()
@APP.route(os.path.join(SERVICE_BASE_URL, 'healthcheck'), methods=['GET'])
def get_healthcheck():
    '''
    Healthcheck response.
    '''
    return "OK\n"


def _check_content_type():
    """
    Check that the POST data is CSV.
    """
    try:
        if request.headers['Content-Type'] != 'text/csv; charset=utf-8':
            raise Exception("Unsupported content type: ", content_type)
    except KeyError:
        pass


def _is_gzipped():
    """
    Is the POST data gzipped?
    """
    try:
        return request.headers['Content-Encoding'] == 'gzip'
    except KeyError:
        pass


@oasis_log_utils.oasis_log()
@APP.route(os.path.join(SERVICE_BASE_URL, 'get_keys'), methods=['POST'])
)
def post_get_keys():
    '''
    Do a lookup on posted location data.
    '''
    data = None
    try:
        lookup_results = []

        _check_content_type()
        is_gzipped = _is_gzipped()
        lookup_results = process_csv(is_gzipped)

        response_data = {
            "status": 'success',
            "items": lookup_results
        }

        data = json.dumps(response_data).encode('utf8')

        if DO_GZIP_RESPONSE:
            data = gzip.zlib.compress(data)

        response = Response(
            data, status=oasis_utils.HTTP_RESPONSE_OK, mimetype="application/json")

        if DO_GZIP_RESPONSE:
            response.headers['Content-Encoding'] = 'gzip'
    except:
        logger.exception("Error in post_lookup")
        response = Response(
            status=oasis_utils.HTTP_RESPONSE_INTERNAL_SERVER_ERROR)
    return response


@oasis_log_utils.oasis_log()
def process_csv(is_gzipped):
    '''
    Process locations posted as CSV data.
    '''
    data = None
    if is_gzipped:
        loc_data = gzip.zlib.decompress(request.data).decode('utf-8')
    else:
        loc_data = request.data.decode('utf-8')

    logger.debug("Processing locations - csv")

    results = []
    for result in keys_lookup.process_locations(loc_data):
        results.append(result)

    logger.info('### Results: {}'.format(results))
    return results


if __name__ == '__main__':
    APP.run(debug=True, host='0.0.0.0', port=5000)
