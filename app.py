"""
Flask application for Oasis keys service.

Currently handles compressed/uncompressed POSTed data. 
Processes the data sequentially - should be made multi-threaded.

"""
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

from oasis_utils import (
    oasis_utils,
    oasis_log_utils,
    oasis_sys_utils,
)

from .utils import (
    get_keys_lookup_instance,
)

# Module-level variables (globals)
APP = None
CONFIG_PARSER = None
logger = None
KEYS_DATA_DIRECTORY = None
MODEL_VERSION_FILE = None
SUPPLIER = None
MODEL_NAME = None
MODEL_VERSION = None
SERVICE_BASE_URL = None
keys_lookup = None


# App initialisation
@oasis_log_utils.oasis_log()
def init():
    """
    App initialisation.
    """
    global APP
    global CONFIG_PARSER
    global logger
    global DO_GZIP_RESPONSE
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

    # Logging configuration
    oasis_log_utils.read_log_config(CONFIG_PARSER)

    logger = logging.getLogger('Starting rotating log.')
    logger.info("Starting keys service.")

    # Get Gzip response and port settings
    DO_GZIP_RESPONSE = CONFIG_PARSER.getboolean('Default', 'DO_GZIP_RESPONSE')
    PORT = CONFIG_PARSER.get('Default', 'PORT')

    # Check that the keys data directory exists
    KEYS_DATA_DIRECTORY = os.path.join(os.sep, 'var', 'oasis', 'keys_data')
    if not os.path.isdir(KEYS_DATA_DIRECTORY):
        raise Exception("Keys data directory not found: {}.".format(KEYS_DATA_DIRECTORY))

    # Check the model version file exists
    MODEL_VERSION_FILE = os.path.join(KEYS_DATA_DIRECTORY, 'ModelVersion.csv')
    if not os.path.isfile(MODEL_VERSION_FILE):
        raise Exception("No model version file: {}.".format(MODEL_VERSION_FILE))

    with open(MODEL_VERSION_FILE) as f:
        SUPPLIER, MODEL_NAME, MODEL_VERSION = map(lambda s: s.strip(), map(tuple, csv.reader(f))[0])
        
    logger.info("Supplier: {}.".format(SUPPLIER))
    logger.info("Model name: {}.".format(MODEL_NAME))
    logger.info("Model version: {}.".format(MODEL_VERSION))

    # Set the web service base URL
    SERVICE_BASE_URL = os.path.join(os.sep, SUPPLIER, MODEL_NAME, MODEL_VERSION)

    # Creating the keys lookup instance
    try:
        keys_lookup = get_keys_lookup_instance(KEYS_DATA_DIRECTORY, SUPPLIER, MODEL_NAME, MODEL_VERSION)
        logging.info("Loaded keys lookup service {}".format(keys_lookup))
    except Exception as e:
        raise Exception("Error in loading keys lookup service: {}.".format(str(e)))

try:
    init()
except Exception as e:
    logger.exception(str(e))


@oasis_log_utils.oasis_log()
@APP.route(os.path.join(SERVICE_BASE_URL, "healthcheck"), methods=['GET'])
def healthcheck():
    """
    Healthcheck response.
    """
    return "OK\n\n"


@oasis_log_utils.oasis_log()
@APP.route(os.path.join(SERVICE_BASE_URL, "get_keys"), methods=['POST'])
def get_keys():
    """
    Do a lookup on posted location data.
    """
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

        logger.info("Processing locations.")

        loc_data = (
            gzip.zlib.decompress(request.data).decode('utf-8') if is_gzipped
            else request.data.decode('utf-8')
        )

        mime_type = (
            oasis_utils.MIME_TYPE_CSV if content_type == oasis_utils.HTTP_REQUEST_CONTENT_TYPE_CSV
            else oasis_utils.MIME_TYPE_JSON
        )

        lookup_results = []
        for location in keys_lookup.process_locations(loc_data, mime_type=mime_type):
            lookup_results.append(location)

        logger.info('### {} Exposure records: {}'.format(len(lookup_results), lookup_results))

        data_dict = {
            "status": 'success',
            "items": lookup_results
        }

        res_data = json.dumps(data_dict).encode('utf8')

        if DO_GZIP_RESPONSE:
            res_data = oasis_sys_utils.compress_data(res_data)

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


if __name__ == '__main__':
    APP.run(debug=True, host='0.0.0.0', port=5000)
