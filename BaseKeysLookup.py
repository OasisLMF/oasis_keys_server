import logging
import os

from oasis_utils import (
    oasis_utils,
    oasis_log_utils,
)

class BaseKeysLookup(object):
    """
    Base implementation of model keys lookup logic.
    """

    @oasis_log_utils.oasis_log()
    def __init__(
        self,
        keys_data_directory=os.path.join('/', 'var', 'oasis', 'keys_data'),
        areas=None,
        vulnerabilities=None,
        location_map=None,
        vulnerability_map=None,
        construction_class=None
    ):
        """
        This replaces init above - initialise the static data required
        for the lookup.
        """
        self.KEYS_DATA_DIRECTORY = keys_data_directory
        self.areas = areas
        self.vulnerabilities = vulnerabilities
        self.location_map = location_map
        self.vulnerability_map = vulnerability_map
        self.construction_class = construction_class


    @oasis_log_utils.oasis_log()
    def process_locations(self, loc_data):
        """
        Read in raw location rows from request CSV data and generate
        exposure records.
        """
        pass


    def _get_location_record(self, raw_loc_item):
        """
        Returns a dict of standard location keys and values based on
        a raw location item, which could be a Pandas or Geopandas dataframe
        row or a string representing a line from a CSV file, or a list or
        tuple.
        """
        pass


    def _get_area_peril_id(self, record):
        """
        Get the area peril ID for a particular location record.
        """
        return oasis_utils.UNKNOWN_ID, "Not implemented"


    def _get_vulnerability_id(self, record):
        """
        Get the vulnerability ID for a particular location record.
        """
        return oasis_utils.UNKNOWN_ID-1, "Not implemented"


    @oasis_log_utils.oasis_log()
    def _get_area_peril_ids(self, loc_data, include_context=True):
        """
        Generates area peril IDs in two modes - if include_context is
        True (default) it will generate location records/rows including
        the area peril IDs, otherwise it will generate pairs of location
        IDs and the corresponding area peril IDs.
        """
        pass


    def _get_lookup_success(self, ap_id, vul_id):
        """
        Determine the status of the keys lookup.
        """
        status = oasis_utils.KEYS_STATUS_SUCCESS
        if ap_id == oasis_utils.UNKNOWN_ID or vul_id == oasis_utils.UNKNOWN_ID:
            status = oasis_utils.KEYS_STATUS_NOMATCH
        return status


    def _to_string(self, val):
        """
        Convert to string, with possible additional formatting.
        """
        return str(val) if val != None else ''


    def _to_int(self, val):
        """
        Parse a string to int
        """
        return None if not val or val == 'n/a' else int(val)


    def _to_float(self, val):
        """
        Parse a string to float
        """
        return None if not val or val == 'NULL' else float(val)
