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
from oasislmf.keys.lookup import OasisLookupFactory as oklf
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

# Module-level variables (globals)
APP = None
config = None
keys_lookup = None
logger = None
SERVICE_BASE_URL = None


# App initialisation
@oasis_log()
def init():
    """
    App initialisation.
    """
    global APP
    global config
    global keys_lookup
    global logger
    global SERVICE_BASE_URL

    # Enable utf8 encoding
    reload(sys)
    sys.setdefaultencoding('utf-8')

    # Get the Flask app
    APP = Flask(__name__)

    # Load INI file into config params dict
    keys_server_ini_fp = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'KeysServer.ini')
    config = load_ini_file(keys_server_ini_fp)
    config['LOG_FILE'] = config['LOG_FILE'].replace('%LOG_DIRECTORY%', config['LOG_DIRECTORY'])

    # Logging configuration
    read_log_config(config)

    logger = logging.getLogger('Starting rotating log.')
    logger.info("Starting keys service.")

    # Check that the keys data directory exists
    keys_data_path = config.get('KEYS_DATA_DIRECTORY') or '/var/oasis/keys_data'
    if not os.path.exists(keys_data_path):
        raise OasisException("Keys data directory not found: {}.".format(keys_data_path))
    logger.info('Keys data directory: {}'.format(keys_data_path))

    # Check the model version file exists
    model_version_fp = os.path.join(keys_data_path, 'ModelVersion.csv')
    if not os.path.exists(model_version_fp):
        raise OasisException("No model version file: {}.".format(model_version_fp))

    with io.open(model_version_fp, 'r', encoding='utf-8') as f:
        supplier_id, model_id, model_version = f.read().strip().split(',')
        
    logger.info("Supplier: {}.".format(supplier_id))
    logger.info("Model ID: {}.".format(model_id))
    logger.info("Model version: {}.".format(model_version))

    # Set the web service base URL
    SERVICE_BASE_URL = '/{}/{}/{}'.format(supplier_id, model_id, model_version)

    # Check the lookup package path exists
    lookup_package_name = config.get('LOOKUP_PACKAGE_NAME') or 'keys_server'
    lookup_package_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), lookup_package_name)

    if not os.path.exists(lookup_package_path):
        raise OasisException('No lookup package path found - expected to be found at {}'.format(lookup_package_path))

    # Instantiate the keys lookup class
    _, keys_lookup = oklf.create(keys_data_path, model_version_fp, lookup_package_path)

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

        try:
            config.setdefault('LOC_PANDAS_DF_OBJECT_DTYPE', False)
            if config['LOC_PANDAS_DF_OBJECT_DTYPE']:
                loc_df = (
                    pd.read_csv(io.StringIO(loc_data), dtype='object', float_precision='high') if content_type == HTTP_REQUEST_CONTENT_TYPE_CSV
                    else pd.read_json(io.StringIO(loc_data))
                )
            else:
                loc_df = (
                    pd.read_csv(io.StringIO(loc_data), float_precision='high') if content_type == HTTP_REQUEST_CONTENT_TYPE_CSV
                    else pd.read_json(io.StringIO(loc_data))
                )
        except pd.errors.EmptyDataError as e:
            raise OasisException(e)

        loc_df = loc_df.where(loc_df.notnull(), None)
        loc_df.columns = loc_df.columns.str.lower()

        res_str = ''

        for i, r in enumerate(keys_lookup.process_locations(loc_df)):
            res_str = '{}{},'.format(res_str, json.dumps(r))

        res_str = res_str.rstrip(',')
        res_str = '{{"status":"success","items":[{}]}}'.format(''.join(res_str))

        logger.info('### {} exposure records generated'.format(i + 1))

        res_data = None

        compress_response = config.get('COMPRESS_RESPONSE') or True

        if compress_response:
            res_data = compress_data(res_str)

        response = Response(
            res_data, status=HTTP_RESPONSE_OK, mimetype=MIME_TYPE_JSON
        )

        if compress_response:
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
