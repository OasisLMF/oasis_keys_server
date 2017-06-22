__all__ = [
	'get_keys_lookup_instance',
	'process_csv',
	'process_json'
]

import gzip

import keys_server

from oasis_utils import (
    oasis_utils,
    oasis_log_utils,
)

# Initialise keys lookup service
@oasis_log_utils.oasis_log()
def get_keys_lookup_instance(
    keys_data_directory,
    supplier,
    model_name,
    model_version
):
    """
    Utility method to create a keys lookup instance for the given supplier,
    model name and version parameters.
    """
    klc = getattr(keys_server, "{}KeysLookup".format(model_name))
    return klc(keys_data_directory, supplier, model_name, model_version)


@oasis_log_utils.oasis_log()
def process_csv(request, keys_lookup, is_gzipped=False):
    """
    Process locations posted as CSV data.
    """
    loc_data = (
        gzip.zlib.decompress(request.data).decode('utf-8') if is_gzipped
        else request.data.decode('utf-8')
    )

    items = []
    for item in keys_lookup.process_locations(loc_data, mime_type=oasis_utils.MIME_TYPE_CSV):
        items.append(item)

    return items


@oasis_log_utils.oasis_log()
def process_json(request, keys_lookup, is_gzipped=False):
    """
    Process locations posted as JSON data.
    """
    loc_data = (
        gzip.zlib.decompress(request.data).decode('utf-8') if is_gzipped
        else request.data.decode('utf-8')
    )

    items = []
    for item in keys_lookup.process_locations(loc_data, mime_type=oasis_utils.MIME_TYPE_JSON):
        items.append(item)

    return items
