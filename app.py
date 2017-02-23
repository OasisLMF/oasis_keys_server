'''
Flask application for Oasis keys service.

Currently handles compressed/uncompressed POSTed data. 
Processes the data sequentially - should be made multi-threaded.

'''
from ConfigParser import ConfigParser
import csv
import inspect
import io
import json
import math
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
logger = logging.getLogger('Rotating log')
logger.info("Starting keys server app.")
model_version_file = os.path.join(KEYS_DATA_DIRECTORY, 'ModelVersion.csv')
if not os.path.isdir(KEYS_DATA_DIRECTORY):
    logger.exception(
        "Keys data directory not found: {}".format(KEYS_DATA_DIRECTORY))
    sys.exit(1)
if not os.path.isfile(model_version_file):
    logger.exception(
        "No model version file: {}".format(model_version_file))
    sys.exit(1)
with open(model_version_file) as f:
    (SUPPLIER, MODEL_NAME, MODEL_VERSION) = f.readline().split(",")
    MODEL_VERSION = MODEL_VERSION.rstrip()
    logger.info("Supplier: {}".format(SUPPLIER))
    logger.info("Model name: {}".format(MODEL_NAME))
    logger.info("Model version: {}".format(MODEL_VERSION))

try:
    logging.info('Initialising keys lookup service.')
    keys_lookup = KeysLookup()
except:
    logger.exception("Error initializing keys lookup service.")
    sys.exit(1)


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
        data = gzip.zlib.decompress(request.data).decode('utf-8')
    else:
        data = request.data.decode('utf-8')

    logger.debug("Processing locations - csv")

    results = []
    reader = csv.reader(io.StringIO(data), delimiter=',')

    #Skip the header
    next(reader)
    for row in reader:
        if row:
            keys_lookup.process_row(row, results)
        else:
            break
        #processed_count += 1
        #if processed_count % 100 == 0:
        #    logging.info("Processed {} locations".format(processed_count))

    apids = keys_lookup._get_area_peril_id_bulk(io.StringIO(data))

    processed_count = 0
    for i in range(len(apids)):
        if not math.isnan(apids[i]):
            apid = int(apids[i])
            results[3*i]['area_peril_id'] = apid
            results[3*i+1]['area_peril_id']= apid
            results[3*i+2]['area_peril_id']= apid
            results[3*i]['status'] = oasis_utils.KEYS_STATUS_SUCCESS
            results[3*i+1]['status'] = oasis_utils.KEYS_STATUS_SUCCESS
            results[3*i+2]['status']= oasis_utils.KEYS_STATUS_SUCCESS
        #if results[3*i]['message'] == "AreaPerilID not implemented":
            #results[3*i]['area_peril_id'] = oasis_utils.UNKNOWN_ID
            #results[3*i+1]['area_peril_id'] = oasis_utils.UNKNOWN_ID
            #results[3*i+2]['area_peril_id'] = oasis_utils.UNKNOWN_ID
            results[3*i]['message'] = ""
            results[3*i+1]['message'] = ""
            results[3*i+2]['message'] = ""
            #results[3*i]['status'] = oasis_utils.KEYS_STATUS_NO_MATCH
            #results[3*i+1]['status'] = oasis_utils.KEYS_STATUS_NO_MATCH
            #results[3*i+2]['status'] = oasis_utils.KEYS_STATUS_NO_MATCH
    logger.info('### post bulk area peril id results={}'.format(results))
    return results

if __name__ == '__main__':
    APP.run(debug=True, host='0.0.0.0', port=5000)
