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

# Module-level variables (globals)
APP = None
CONFIG_PARSER = None
RUN_MODE = None
logger = None
KEYS_DATA_DIRECTORY = None
MODEL_VERSION_FILE = None
SUPPLIER = None
MODEL_NAME = None
MODEL_VERSION = None
SERVICE_BASE_URL = None
keys_lookup = None


# Initialise keys lookup service
@oasis_log_utils.oasis_log()
def get_keys_lookup(
    keys_data_directory,
    supplier,
    model_name,
    model_version
):
    klc = getattr(keys_server, "{}KeysLookup".format(model_name))
    return klc(keys_data_directory, supplier, model_name, model_version)


# App initialisation
@oasis_log_utils.oasis_log()
def init():
    global APP
    global CONFIG_PARSER
    global RUN_MODE
    global logger
    global KEYS_DATA_DIRECTORY
    global MODEL_VERSION_FILE
    global MODEL_NAME
    global MODEL_VERSION
    global SERVICE_BASE_URL
    global keys_lookup

    # Enable utf8 encoding
    reload(sys)
    sys.setdefaultencoding('utf-8')

    # Get the Flask app
    APP = Flask(__name__)

    # Load keys server config settings
    CONFIG_PARSER = ConfigParser()
    cwd = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
    CONFIG_PARSER.read(os.path.abspath(os.path.join(cwd, 'KeysServer.ini')))

    # Get run mode - could be 'live' if production mode or 'test' if not. This
    # could be used to conditionally execute or not execute parts of the
    # initialisation code
    RUN_MODE = CONFIG_PARSER.get('Default', 'RUN_MODE')

    # Logging configuration
    oasis_log_utils.read_log_config(CONFIG_PARSER)

    logger = logging.getLogger('Starting rotating log.')
    logger.info("Starting keys server app.")

    # Get Gzip response and port settings
    DO_GZIP_RESPONSE = CONFIG_PARSER.getboolean('Default', 'DO_GZIP_RESPONSE')
    PORT = CONFIG_PARSER.get('Default', 'PORT')

    # Check that the keys data directory exists
    KEYS_DATA_DIRECTORY = os.path.join(os.sep, 'var', 'oasis', 'keys_data')
    if not os.path.isdir(KEYS_DATA_DIRECTORY):
        logger.exception(
            "Keys data directory not found: {}.".format(KEYS_DATA_DIRECTORY)
        )
        sys.exit(1)

    # Check the model version file exists
    MODEL_VERSION_FILE = os.path.join(KEYS_DATA_DIRECTORY, 'ModelVersion.csv')
    if not os.path.isfile(MODEL_VERSION_FILE):
        logger.exception(
            "No model version file: {}.".format(MODEL_VERSION_FILE)
        )
        sys.exit(1)

    with open(MODEL_VERSION_FILE) as f:
        SUPPLIER, MODEL_NAME, MODEL_VERSION = map(lambda s: s.strip(), map(tuple, csv.reader(f))[0])
        
    logger.info("Supplier: {}.".format(SUPPLIER))
    logger.info("Model name: {}.".format(MODEL_NAME))
    logger.info("Model version: {}.".format(MODEL_VERSION))

    # Set the web service base URL
    SERVICE_BASE_URL = os.path.join(os.sep, SUPPLIER, MODEL_NAME, MODEL_VERSION)

    # Creating the keys lookup instance
    try:
        keys_lookup = get_keys_lookup(KEYS_DATA_DIRECTORY, SUPPLIER, MODEL_NAME, MODEL_VERSION)
        logging.info("Loaded keys lookup service {}".format(keys_lookup))
    except Exception as e:
        logger.exception("Error in loading keys lookup service: {}.".format(str(e)))
        sys.exit(1)

init()


@oasis_log_utils.oasis_log()
@APP.route(os.path.join(SERVICE_BASE_URL, "healthcheck"), methods=['GET'])
def get_healthcheck():
    '''
    Healthcheck response.
    '''
    return "OK\n"


@oasis_log_utils.oasis_log()
@APP.route(os.path.join(SERVICE_BASE_URL, "get_keys"), methods=['POST'])
def get_keys():
    '''
    Do a lookup on posted location data.
    '''
    response = res_data = None

    try:
        try:
            content_type = request.headers['Content-Type']
        except KeyError:
            pass
        else:
            if content_type not in [
                oasis_utils.HTTP_REQUEST_CONTENT_TYPE_CSV,
                oasis_utils.HTTP_REQUEST_CONTENT_TYPE_JSON
            ]:
                raise Exception('Unsupported content type: "{}"'.format(content_type))

        try:
            is_gzipped = request.headers['Content-Encoding'] == 'gzip'
        except KeyError:
            is_gzipped = False

        lookup_results = (
            process_csv(is_gzipped) if content_type == oasis_utils.HTTP_REQUEST_CONTENT_TYPE_CSV
            else process_json(is_gzipped)
        )

        data_dict = {
            "status": 'success',
            "items": lookup_results
        }

        res_data = json.dumps(data_dict).encode('utf8')

        if DO_GZIP_RESPONSE:
            res_data = gzip.zlib.compress(res_data)

        response = Response(
            res_data, status=oasis_utils.HTTP_RESPONSE_OK, mimetype=oasis_utils.MIME_TYPE_JSON
        )

        if DO_GZIP_RESPONSE:
            response.headers['Content-Encoding'] = 'gzip'
    except Exception as e:
        logger.exception("Keys lookup error: {}.".format(str(e)))
        response = Response(
            status=oasis_utils.HTTP_RESPONSE_INTERNAL_SERVER_ERROR
        )
    finally:
        return response


@oasis_log_utils.oasis_log()
def process_csv(is_gzipped=False):
    '''
    Process locations posted as CSV data.
    '''
    loc_data = (
        gzip.zlib.decompress(request.data).decode('utf-8') if is_gzipped
        else request.data.decode('utf-8')
    )

    logger.debug("Processing locations.")

    results = []
    for result in keys_lookup.process_locations(loc_data, mime_type=oasis_utils.MIME_TYPE_CSV):
        results.append(result)

    logger.info('### {} Exposure records: {}'.format(len(results), results))
    return results


@oasis_log_utils.oasis_log()
def process_json(is_gzipped=False):
    '''
    Process locations posted as JSON data.
    '''
    loc_data = (
        gzip.zlib.decompress(request.data).decode('utf-8') if is_gzipped
        else request.data.decode('utf-8')
    )

    logger.debug("Processing locations.")

    results = []
    for result in keys_lookup.process_locations(loc_data, mime_type=oasis_utils.MIME_TYPE_JSON):
        results.append(result)

    logger.info('### {} Exposure records: {}'.format(len(results), results))
    return results


if __name__ == '__main__':
    init()
    APP.run(debug=True, host='0.0.0.0', port=5000)
