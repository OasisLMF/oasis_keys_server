import logging
from oasis_utils import oasis_utils, oasis_log_utils

class BaseKeysLookup(object):
    """
    Base implementation of model keys lookup logic.
    """

    peril_id = oasis_utils.UNKNOWN_ID

    @oasis_log_utils.oasis_log()
    def init(self, keys_data_directory):
        """
        Initialise the static data required for the lookup.
        """
        pass

    @oasis_log_utils.oasis_log()
    def process_row(self, row, results):
        """
        Process a location row, and add the results of the
        lookup to the results.
        """
        record = None
        row_failed = False
        for coverage_type in (
                oasis_utils.BUILDING_COVERAGE_CODE, oasis_utils.CONTENTS_COVERAGE_CODE):
            try:
                if record is None:
                    record = self._read_record(row)
                record['coverage_type'] = coverage_type
                ap_id, area_peril_message = self._get_area_peril_id(record)
                vul_id, vulnerability_message = self._get_vulnerability_id(record)
            except:
                row_failed = True
                logging.exception("Error processing row: {}".format(row))

            if row_failed:
                status = oasis_utils.KEYS_STATUS_FAIL
            else:
                status = self._get_lookup_success(ap_id, vul_id)

            exposure_record = {
                'id': record['loc_id'],
                'peril_id': oasis_utils.PERIL_ID_QUAKE,
                'coverage': coverage_type,
                'area_peril_id': self.peril_id,
                'vulnerability_id': vul_id,
                'message': "{} - {}".format(
                    area_peril_message, vulnerability_message),
                'status': status
            }
            results.append(exposure_record)

    def _read_record(self, line):
        """
        Parse a line from the CSV data
        """
        vals = [x.strip().upper() for x in line]
        vals.reverse()
        return {
            'loc_id': self._to_int(vals.pop()),
            'accntnum': vals.pop().strip(),
            'locnum': self._to_int(vals.pop()),
            'city': vals.pop().strip(),
            'state': vals.pop().strip(),
            'latitude': self._to_float(vals.pop()),
            'longitude': self._to_float(vals.pop()),
            'addrmatch': self._to_int(vals.pop()),
            'country': vals.pop().strip(),
            'numbldgs': self._to_int(vals.pop()),
            'bldgscheme': vals.pop().strip(),
            'bldgclass': vals.pop().strip(),
            'occscheme': vals.pop().strip(),
            'occtype': self._to_int(vals.pop()),
            'cntryscheme': vals.pop().strip(),
            'cntrycode': vals.pop().strip(),
            'cv1val': self._to_float(vals.pop()),
            'cv2val': self._to_float(vals.pop()),
        }

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

    def _get_lookup_success(self, ap_id, vul_id):
        """
        Determine the status of the keys lookup.
        """
        status = oasis_utils.KEYS_STATUS_SUCCESS
        if ap_id == oasis_utils.UNKNOWN_ID or vul_id == oasis_utils.UNKNOWN_ID:
            status = oasis_utils.KEYS_STATUS_NOMATCH
        return status

    def _to_int(self, val):
        """
        Parse a string to int
        """
        if val == 'n/a':
            return None
        return int(val)

    def _to_float(self, val):
        """
        Parse a string to float
        """
        if not val or val == 'NULL':
            return None
        return float(val)
