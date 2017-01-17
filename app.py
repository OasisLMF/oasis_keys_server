﻿'''
Flask application for Oasis keys service.

Currently handles compressed/uncompressed POSTed data. 
Processes the data sequentially - could be made multi-threaded.

'''
from ConfigParser import ConfigParser
import csv
import inspect
import io
import json
import os
import sys
import gzip
import logging
from keys_server.KeysLookup import KeysLookup
from flask import Flask, Response, request
from oasis_utils import oasis_utils, oasis_log_utils

# Enable utf8 encoding
reload(sys)
sys.setdefaultencoding('utf-8')

APP = Flask(__name__)

CONFIG_PARSER = ConfigParser()
CURRENT_DIRECTORY = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
INI_PATH = os.path.abspath(os.path.join(CURRENT_DIRECTORY, 'KeysServer.ini'))
CONFIG_PARSER.read(INI_PATH)

# Logging configuration
oasis_log_utils.read_log_config(CONFIG_PARSER)

DO_GZIP_RESPONSE = CONFIG_PARSER.getboolean('Default', 'DO_GZIP_RESPONSE')
PORT = CONFIG_PARSER.get('Default', 'PORT')
KEYS_DATA_DIRECTORY = '/var/oasis/keys_data'

# Load the keys data
logging.getLogger().info("Starting load keys data.")
model_version_file = os.path.join(KEYS_DATA_DIRECTORY, 'ModelVersion.csv')
if not os.path.isdir(KEYS_DATA_DIRECTORY):
    logging.getLogger().exception(
        "Keys data directory not found: {}".format(KEYS_DATA_DIRECTORY))
    exit()
if not os.path.isfile(model_version_file):
    logging.getLogger().exception(
        "No model version file: {}".format(model_version_file))
    exit()
with open(model_version_file) as f:
    (SUPPLIER, MODEL_NAME, MODEL_VERSION) = f.readline().split(",")
    MODEL_VERSION = MODEL_VERSION.rstrip()
    logging.getLogger().info("Supplier: {}".format(SUPPLIER))
    logging.getLogger().info("Model name: {}".format(MODEL_NAME))
    logging.getLogger().info("Model version: {}".format(MODEL_VERSION))

try:
    keys_lookup = KeysLookup()
    keys_lookup.init(KEYS_DATA_DIRECTORY)
except:
    logging.getLogger().exception("Error initializing lookup")
    exit()


@oasis_log_utils.oasis_log()
@APP.route(
    '/{}/{}/{}/healthcheck'.format(SUPPLIER, MODEL_NAME, MODEL_VERSION),
    methods=['GET'])
def get_healthcheck():
    '''
    Healthcheck response.
    '''
    return "OK"

def _check_content_type():
    """
    Check that the POST data is CSV.
    """
    content_type = ''
    if 'Content-Type' in request.headers:
        content_type = request.headers['Content-Type']
    if content_type != 'text/csv; charset=utf-8':
        raise Exception("Unsupported content type: ", content_type)


def _is_gzipped():
    """
    Is the POST data gzipped?
    """
    is_gzipped = False
    if 'Content-Encoding' in request.headers:
        content_encoding = request.headers['Content-Encoding']
        is_gzipped = (content_encoding == 'gzip')
    return is_gzipped

@oasis_log_utils.oasis_log()
@APP.route(
    '/{}/{}/{}/get_keys'.format(SUPPLIER, MODEL_NAME, MODEL_VERSION),
    methods=['POST'])
def post_get_keys():
    '''
    Do a lookup on posted location data.
    '''
    data = None
    try:
        lookup_results = list()

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
        logging.getLogger().exception("Error in post_lookup")
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
        data = gzip.zlib.decompress(request.data).decode('utf-8')
    else:
        data = request.data.decode('utf-8')

    logging.getLogger().debug("Processing locations - csv")

    results = list()
    reader = csv.reader(io.StringIO(data), delimiter=',')

    #Skip the header
    next(reader)
    processed_count = 0
    for row in reader:
        keys_lookup.process_row(row, results)
        processed_count = processed_count + 1
        if processed_count % 100 == 0:
            logging.info("Processed {} locations".format(processed_count))

    return results
