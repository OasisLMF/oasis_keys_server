# -*- coding: utf-8 -*-

"""
Flask application for Oasis keys service.

Currently handles compressed/uncompressed POSTed data. 
Processes the data sequentially - should be made multi-threaded.

"""
# Standard libraries
import csv
import io
import json
import logging
import os
import sys

from configparser import ConfigParser

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
from oasislmf.keys.lookup import OasisLookup
from oasislmf.utils.compress import compress_data
from oasislmf.utils.conf import load_ini_file
from oasislmf.utils.exceptions import OasisException
from oasislmf.utils.log import set_rotating_logger
from oasislmf.utils.http import (
    HTTP_REQUEST_CONTENT_TYPE_CSV,
    HTTP_REQUEST_CONTENT_TYPE_JSON,
    HTTP_RESPONSE_INTERNAL_SERVER_ERROR,
    HTTP_RESPONSE_OK,
    MIME_TYPE_JSON,
)
from oasislmf.utils.log import oasis_log

# Module-level variables (globals)
APP2 = None
config_parser = None
oasis_lookup = None
logger = None
SERVICE_BASE_URL = None


# App initialisation
@oasis_log()
def init():
    """
    App initialisation.
    """
    global APP2
    global config_parser
    global oasis_lookup
    global logger
    global SERVICE_BASE_URL

    # Enable utf8 encoding
    reload(sys)
    sys.setdefaultencoding('utf-8')

    # Get the Flask app
    APP2 = Flask(__name__)

    # Create config_parser.parser and load with keys server INI file
    config_parser = ConfigParser()
    cwd = os.path.dirname(__file__)

    keys_server_ini_fp = os.path.join(cwd, 'KeysServer.ini')
    if not os.path.exists(keys_server_ini_fp):
        raise OasisException('No `KeysServer.ini` file found in app directory')

    config_parser.read(keys_server_ini_fp)

    # Check that the keys data directory exists
    keys_data_path = config_parser.get('Lookup', 'KEYS_DATA_PATH') or '/var/oasis/keys_data'
    if not os.path.exists(keys_data_path):
        raise OasisException("Keys data directory not found: {}.".format(keys_data_path))

    log_dir = config_parser.get('Default', 'LOG_DIRECTORY') or keys_data_path
    log_fname = (config_parser.get('Default', 'LOG_FILE_PATH') or 'keys_server.log').split(os.path.sep)[-1]
    log_fp = os.path.join(log_dir, log_fname)
    config_parser.set('Default', 'LOG_FILE_PATH', log_fp)

    log_level = config_parser.get('Default', 'LOG_LEVEL') or logging.INFO
    max_file_size = config_parser.getint('Default', 'LOG_MAX_SIZE_IN_BYTES') or 10**7
    max_backups = config_parser.getint('Default', 'LOG_BACKUP_COUNT') or 5

    # Logging configuration
    set_rotating_logger(log_fp, log_level, max_file_size, max_backups)

    logger = logging.getLogger('\nStarting rotating log.')
    logger.info("\nStarting keys service.")

    logger.info('\nKeys data path: {}'.format(keys_data_path))

    # Check the model version file exists
    model_version_fp = os.path.join(keys_data_path, 'ModelVersion.csv')
    if not os.path.exists(model_version_fp):
        raise OasisException("No model version file: {}.".format(model_version_fp))

    with io.open(model_version_fp, 'r', encoding='utf-8') as f:
        supplier_id, model_id, model_version = map(lambda s: s.strip(), map(tuple, csv.reader(f))[0])
        
    logger.info("\nSupplier: {}.".format(supplier_id))
    logger.info("Model ID: {}.".format(model_id))
    logger.info("Model version: {}.".format(model_version))

    # Set the web service base URL
    SERVICE_BASE_URL = '/{}/{}/{}'.format(supplier_id, model_id, model_version)

    # Check the lookup config JSON file exists in the keys data
    lookup_config_fp = config_parser.get('Lookup', 'CONFIG_FILE_PATH').replace('%KEYS_DATA_PATH%', keys_data_path)

    if not os.path.exists(lookup_config_fp):
        raise OasisException('No lookup config file {} found in the keys data directory'.format(lookup_config_fp))

    config_parser.set('Lookup', 'CONFIG_FILE_PATH', lookup_config_fp)

    logger.info('\nLoading lookup config from file {}'.format(lookup_config_fp))

    with io.open(lookup_config_fp, 'r+', encoding='utf-8') as f:
        lookup_config = json.load(f)

        lookup_config['keys_data_path'] = keys_data_path
        lookup_config['peril']['file_path'] = os.path.abspath(
            lookup_config['vulnerability']['file_path'].replace('%%KEYS_DATA_PATH%%', keys_data_path)
        )
        lookup_config['vulnerability']['file_path'] = os.path.abspath(
            lookup_config['vulnerability']['file_path'].replace('%%KEYS_DATA_PATH%%', keys_data_path)
        )
        lookup_config['peril']['rtree_index']['filename'] = os.path.abspath(
            lookup_config['peril']['rtree_index']['filename'].replace('%%KEYS_DATA_PATH%%', keys_data_path)
        )

    logger.info('\nLoaded lookup config: {}'.format(lookup_config))

    # Instantiate the keys lookup class
    oasis_lookup = OasisLookup(config=lookup_config)

try:
    init()
except Exception as e:
    all_vars_dict = dict(globals())
    all_vars_dict.update(locals())
    if all_vars_dict['logger']:
        logger.exception(str(e))


@oasis_log()
@APP2.route('{}/healthcheck'.format(SERVICE_BASE_URL) if SERVICE_BASE_URL else '/healthcheck', methods=['GET'])
def healthcheck():
    """
    Healthcheck response.
    """
    return "OK"


@oasis_log()
@APP2.route('{}/get_keys'.format(SERVICE_BASE_URL) if SERVICE_BASE_URL else '/get_keys', methods=['POST'])
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
        for r in oasis_lookup.bulk_lookup(loc for _, loc in loc_df.iterrows()):
            n += 1
            res_str = '{}{},'.format(res_str, json.dumps(r))

        res_str = res_str.rstrip(',')
        res_str = '{{"status":"success","items":[{}]}}'.format(''.join(res_str))

        logger.info('### {} exposure records generated'.format(n))

        res_data = None

        compress_response = config_parser.getboolean('Default', 'COMPRESS_RESPONSE') or True

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
    APP2.run(debug=True, host='0.0.0.0', port=5000)
