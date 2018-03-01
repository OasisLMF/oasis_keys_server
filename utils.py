# -*- coding: utf-8 -*-

__all__ = [
    'get_keys_lookup_instance'
]

import keys_server

from oasislmf.utils.exceptions import OasisException

from oasislmf.utils.log import oasis_log

# Initialise keys lookup service
@oasis_log()
def get_keys_lookup_instance(
    keys_data_directory,
    supplier_id,
    model_id,
    model_version_id
):
    """
    Utility method to create a keys lookup instance for the given supplier ID,
    model ID and model version ID.
    """
    try:
        klc = getattr(keys_server, "{}KeysLookup".format(model_id))
    except AttributeError as e:
        raise OasisException(e)

    return klc(keys_data_directory, supplier_id, model_id, model_version_id)
