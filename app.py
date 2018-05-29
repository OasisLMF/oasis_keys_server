# -*- coding: utf-8 -*-

"""
Flask application for Oasis keys service.

Currently handles compressed/uncompressed POSTed data. 
Processes the data sequentially - should be made multi-threaded.

"""
# Standard libraries
import csv
import inspect
import io
import json
import logging
import os
import sys

from gzip import zlib
from tempfile import NamedTemporaryFile
from zlib import error as ZlibError

# Custom libraries
import pandas as pd

from flask import (
    Flask,
    request,
    Response,
)

from werkzeug.exceptions import HTTPException

# Oasis libraries
from oasislmf.utils.compress import compress_data
from oasislmf.utils.conf import load_ini_file
from oasislmf.utils.exceptions import OasisException
from oasislmf.utils.http import (
    HTTP_REQUEST_CONTENT_TYPE_CSV,
    HTTP_REQUEST_CONTENT_TYPE_JSON,
    HTTP_RESPONSE_INTERNAL_SERVER_ERROR,
    HTTP_RESPONSE_OK,
    MIME_TYPE_JSON,
)
from oasislmf.utils.log import (
    oasis_log,
    read_log_config,
)

# `oasis_keys_server` imports
from utils import (
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
COMPRESS_RESPONSE = False


# App initialisation
@oasis_log()
def init():
    """
    App initialisation.
    """
    global APP
    global KEYS_SERVER_INI_FILE
    global CONFIG_PARSER
    global logger
    global COMPRESS_RESPONSE
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
    CONFIG_PARSER = load_ini_file(KEYS_SERVER_INI_FILE)
    CONFIG_PARSER['LOG_FILE'] = CONFIG_PARSER['LOG_FILE'].replace('%LOG_DIRECTORY%', CONFIG_PARSER['LOG_DIRECTORY'])

    # Logging configuration
    read_log_config(CONFIG_PARSER)

    logger = logging.getLogger('Starting rotating log.')
    logger.info("Starting keys service.")

    # Get Gzip response and port settings
    COMPRESS_RESPONSE = bool(CONFIG_PARSER['COMPRESS_RESPONSE'])

    # Check that the keys data directory exists
    KEYS_DATA_DIRECTORY = CONFIG_PARSER['KEYS_DATA_DIRECTORY']
    if not os.path.isdir(KEYS_DATA_DIRECTORY):
        raise OasisException("Keys data directory not found: {}.".format(KEYS_DATA_DIRECTORY))
    logger.info('Keys data directory: {}'.format(KEYS_DATA_DIRECTORY))

    # Check the model version file exists
    MODEL_VERSION_FILE = os.path.join(KEYS_DATA_DIRECTORY, 'ModelVersion.csv')
    if not os.path.exists(MODEL_VERSION_FILE):
        raise OasisException("No model version file: {}.".format(MODEL_VERSION_FILE))

    with io.open(MODEL_VERSION_FILE, 'r', encoding='utf-8') as f:
        SUPPLIER, MODEL_NAME, MODEL_VERSION = map(lambda s: s.strip(), map(tuple, csv.reader(f))[0])
        
    logger.info("Supplier: {}.".format(SUPPLIER))
    logger.info("Model name: {}.".format(MODEL_NAME))
    logger.info("Model version: {}.".format(MODEL_VERSION))

    # Set the web service base URL
    SERVICE_BASE_URL = '/{}/{}/{}'.format(SUPPLIER, MODEL_NAME, MODEL_VERSION)

    # Creating the keys lookup instance
    try:
        keys_lookup = get_keys_lookup_instance(KEYS_DATA_DIRECTORY, SUPPLIER, MODEL_NAME, MODEL_VERSION)
        logger.info("Loaded keys lookup service {}".format(keys_lookup))
    except OasisException as e:
        raise OasisException("Error in loading keys lookup service: {}.".format(str(e)))

try:
    init()
except Exception as e:
    all_vars_dict = dict(globals())
    all_vars_dict.update(locals())
    if all_vars_dict['logger']:
        logger.exception(str(e))


@oasis_log()
@APP.route('{}/healthcheck'.format(SERVICE_BASE_URL) if SERVICE_BASE_URL else '/healthcheck', methods=['GET'])
def healthcheck():
    """
    Healthcheck response.
    """
    return "OK"


@oasis_log()
@APP.route('{}/get_keys'.format(SERVICE_BASE_URL) if SERVICE_BASE_URL else '/get_keys', methods=['POST'])
def get_keys():
    """
    Do a lookup on posted location data.
    """
    response = res_data = None

    try:
        try:
            content_type = request.headers['Content-Type']
        except KeyError:
            raise OasisException('Error: keys request is missing the "Content-Type" header')
        else:
            if content_type not in [
                HTTP_REQUEST_CONTENT_TYPE_CSV,
                HTTP_REQUEST_CONTENT_TYPE_JSON
            ]:
                raise OasisException('Error: unsupported content type: "{}"'.format(content_type))

        try:
            is_gzipped = request.headers['Content-Encoding'] == 'gzip'
        except KeyError:
            is_gzipped = False

        logger.info("Processing locations.")

        loc_data = (
            zlib.decompress(request.data).decode('utf-8') if is_gzipped
            else request.data.decode('utf-8')
        )

        loc_df = (
            pd.read_csv(io.StringIO(loc_data), float_precision='high') if content_type == HTTP_REQUEST_CONTENT_TYPE_CSV
            else pd.read_json(io.StringIO(loc_data))
        )
        loc_df = loc_df.where(loc_df.notnull(), None)
        loc_df.columns = loc_df.columns.str.lower()

        res_str = ''

        n = 0
        for r in keys_lookup.process_locations(loc_df):
            n += 1
            res_str += '{},'.format(json.dumps(r))

        res_str = res_str.rstrip(',')
        res_str = '{{"status":"success","items":[{}]}}'.format(''.join(res_str))

        logger.info('### {} exposure records generated'.format(n))

        res_data = None

        if COMPRESS_RESPONSE:
            res_data = compress_data(res_str)

        response = Response(
            res_data, status=HTTP_RESPONSE_OK, mimetype=MIME_TYPE_JSON
        )

        if COMPRESS_RESPONSE:
            response.headers['Content-Encoding'] = 'deflate'
            response.headers['Content-Length'] = str(len(res_data))
    except (IndexError, HTTPException, IOError, KeyError, MemoryError, OasisException, OSError, TypeError, ValueError, ZlibError) as e:
        logger.exception("Error: {}.".format(str(e)))
        response = Response(
            status=HTTP_RESPONSE_INTERNAL_SERVER_ERROR
        )
    finally:
        return response


if __name__ == '__main__':
    APP.run(debug=True, host='0.0.0.0', port=5000)
