# -*- coding: utf-8 -*-

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
import pandas as pd
import os
import sys

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
KEYS_SERVER_INI_FILE = os.path.join(os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe()))), 'KeysServer.ini')
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
    global KEYS_SERVER_INI_FILE
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

    # Load INI file into config params dict
    CONFIG_PARSER = oasis_sys_utils.load_ini_file(KEYS_SERVER_INI_FILE)
    CONFIG_PARSER['LOG_FILE'] = CONFIG_PARSER['LOG_FILE'].replace('%LOG_DIRECTORY%', CONFIG_PARSER['LOG_DIRECTORY'])

    # Logging configuration
    oasis_log_utils.read_log_config(CONFIG_PARSER)

    logger = logging.getLogger('Starting rotating log.')
    logger.info("Starting keys service.")

    # Get Gzip response and port settings
    DO_GZIP_RESPONSE = bool(CONFIG_PARSER['DO_GZIP_RESPONSE'])

    # Check that the keys data directory exists
    KEYS_DATA_DIRECTORY = CONFIG_PARSER['KEYS_DATA_DIRECTORY']
    if not os.path.isdir(KEYS_DATA_DIRECTORY):
        raise Exception("Keys data directory not found: {}.".format(KEYS_DATA_DIRECTORY))
    logger.info('Keys data directory: {}'.format(KEYS_DATA_DIRECTORY))

    # Check the model version file exists
    MODEL_VERSION_FILE = os.path.join(KEYS_DATA_DIRECTORY, 'ModelVersion.csv')
    if not os.path.exists(MODEL_VERSION_FILE):
        raise Exception("No model version file: {}.".format(MODEL_VERSION_FILE))

    with io.open(MODEL_VERSION_FILE, 'r', encoding='utf-8') as f:
        SUPPLIER, MODEL_NAME, MODEL_VERSION = map(lambda s: s.strip(), map(tuple, csv.reader(f))[0])
        
    logger.info("Supplier: {}.".format(SUPPLIER))
    logger.info("Model name: {}.".format(MODEL_NAME))
    logger.info("Model version: {}.".format(MODEL_VERSION))

    # Set the web service base URL
    SERVICE_BASE_URL = os.path.join(os.sep, SUPPLIER, MODEL_NAME, MODEL_VERSION)

    # Creating the keys lookup instance
    try:
        keys_lookup = get_keys_lookup_instance(KEYS_DATA_DIRECTORY, SUPPLIER, MODEL_NAME, MODEL_VERSION)
        logger.info("Loaded keys lookup service {}".format(keys_lookup))
    except Exception as e:
        raise Exception("Error in loading keys lookup service: {}.".format(str(e)))

try:
    init()
except Exception as e:
    all_vars_dict = dict(globals())
    all_vars_dict.update(locals())
    if all_vars_dict['logger']:
        logger.exception(str(e))


@oasis_log_utils.oasis_log()
@APP.route(os.path.join(SERVICE_BASE_URL if SERVICE_BASE_URL else '/', "healthcheck"), methods=['GET'])
def healthcheck():
    """
    Healthcheck response.
    """
    return "OK"


@oasis_log_utils.oasis_log()
@APP.route(os.path.join(SERVICE_BASE_URL if SERVICE_BASE_URL else '/', "get_keys"), methods=['POST'])
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

        loc_df = (
            pd.read_csv(io.StringIO(loc_data), float_precision='high') if content_type == oasis_utils.HTTP_REQUEST_CONTENT_TYPE_CSV
            else pd.read_json(io.StringIO(loc_data))
        )
        loc_df = loc_df.where(loc_df.notnull(), None)
        loc_df.columns = loc_df.columns.str.lower()

        lookup_results = []
        for record in keys_lookup.process_locations(loc_df):
            lookup_results.append(record)

        logger.info('### {} exposure records generated'.format(len(lookup_results)))

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
            response.headers['Content-Encoding'] = 'deflate'
            response.headers['Content-Length'] = str(len(res_data))
    except Exception as e:
        logger.exception("Keys lookup error: {}.".format(str(e)))
        response = Response(
            status=oasis_utils.HTTP_RESPONSE_INTERNAL_SERVER_ERROR
        )
    finally:
        return response


if __name__ == '__main__':
    APP.run(debug=True, host='0.0.0.0', port=5000)
