# -*- coding: utf-8 -*-

__all__ = [
    'get_keys_lookup_instance'
]

import keys_server

from oasis_utils import (
    OasisException,
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
    try:
        klc = getattr(keys_server, "{}KeysLookup".format(model_name))
    except AttributeError as e:
        raise OasisException(e)

    return klc(keys_data_directory, supplier, model_name, model_version)
