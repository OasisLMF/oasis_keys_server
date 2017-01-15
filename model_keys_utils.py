import os.path
import math
import logging
from oasis_utils import oasis_utils, oasis_log_utils

EARTH_RADIUS = 6378.137
CATRISKS_BUILDING_COVERAGE_CODE = "B"
CATRISKS_CONTENTS_COVERAGE_CODE = "C"

areas = None
vulnerabilities = None
location_map = None
vulnerability_map = None
construction_class = None

@oasis_log_utils.oasis_log()
def init(keys_data_directory):
    """
    Initialise the static data required for the lookup.
    """
    global areas
    global vulnerabilities
    global location_map
    global vulnerability_map 
    global construction_class

    area_file = \
        os.path.join(keys_data_directory, 'DictAreaPeril.csv')
    vul_file = \
        os.path.join(keys_data_directory, 'DictVULNERABILITY.csv')
    areas = read_areas(area_file)
    vulnerabilities = read_vulnerabilities(vul_file)
    location_map = read_location_mappings(keys_data_directory)
    vulnerability_map = read_vulnerability_mappings(keys_data_directory)
    construction_class = read_construction_classes(keys_data_directory)


def _get_lookup_success(ap_id, vul_id):
    status = oasis_utils.KEYS_STATUS_SUCCESS
    if ap_id == -1 or vul_id == -1:
        status = oasis_utils.KEYS_STATUS_NOMATCH
    return status


def process_row (row, results):
    record = None
    row_failed = False
    for coverage_type, catrisks_coverage_type in (
            (oasis_utils.BUILDING_COVERAGE_CODE, CATRISKS_BUILDING_COVERAGE_CODE),
            (oasis_utils.CONTENTS_COVERAGE_CODE, CATRISKS_CONTENTS_COVERAGE_CODE)):
        try:
            # To fix - see set_coverage function
            if record is None:
                record = read_record(row)
            record['coverage_type'] = catrisks_coverage_type
            fix_locations_by_dictionary(record, location_map)
            ap_id, mes1 = get_area_peril_id(record, areas)
            vul_id, mes2 = get_vulnerability_id(
                record, vulnerabilities, vulnerability_map, construction_class)
        except:
            row_failed = True
            logging.exception("Error processing row: {}".format(row))

        if row_failed:
            status = oasis_utils.KEYS_STATUS_FAIL
        else:
            status = _get_lookup_success(ap_id, vul_id)

        exposure_record = {
            'id': record['item_id'],
            'peril_id': oasis_utils.PERIL_ID_QUAKE,
            'coverage': coverage_type,
            'area_peril_id': ap_id,
            'vulnerability_id': vul_id,
            'message': mes1 + mes2,
            'status': status
        }
        results.append(exposure_record)


def get_area_peril_id(record, areas):
    if not record['country']:
        return -1, 'The country code could not be empty'

    do_list = [
        ('VRG', get_area_peril_id_based_on_lonlat),
        ('AREALEVEL_5', get_area_peril_id_based_on_city),
        ('AREALEVEL_2', get_area_peril_id_based_on_province),
        ('AREALEVEL_1', get_area_peril_id_based_on_country),
    ]

    if not record['longitude']:
        do_list = do_list[1:]

    message = ''
    for (agg_level, peril_func) in do_list:
        sub_areas = list(filter(lambda r: r['aggregation_level'] == agg_level, areas))
        area_peril_id, mes = peril_func(record, sub_areas)
        message += mes
        if area_peril_id:
            return area_peril_id, message

    return -1, message


def get_area_peril_id_builder(match_func, found_message, not_found_message):
    def get_area_peril_id_with_match(record, areas):
        try:
            area = next(a for a in areas if match_func())
            return area['areaperil_id'], found_message
        except StopIteration:
            return None, not_found_message
    return get_area_peril_id_with_match

def get_area_peril_id_based_on_country(record, areas):
    try:
        area = next(a for a in areas if record['country'] == a['arealevel_1'].upper())
        return area['areaperil_id'], 'Mapped by Country name! {}'.format(area['areaperil_id'])
    except StopIteration:
        return None, 'Country name was not found for: {}'.format(record['country'])

def get_area_peril_id_based_on_province(record, areas):
    try:
        area = next(a for a in areas if record['state'] == a['arealevel_2'].upper())
        if record['country'] == area['arealevel_1']:
            return area['areaperil_id'], 'Mapped by Province name!{}'.format(area['areaperil_id'])
        else:
            return None, "Given Province is in another Country! found AreaPeril_ID= {}".format(area['areaperil_id'])
    except StopIteration:
        return None, ''

def get_area_peril_id_based_on_city(record, areas):
    try:
        area = next(a for a in areas if record['city'] == a['arealevel_5'].upper())
        if record['country'] == area['arealevel_1']:
            return area['areaperil_id'], 'Mapped by City name!{}'.format(area['areaperil_id'])
        else:
            return None, "Given City is in another Country! found AreaPeril_ID= {}".format(area['areaperil_id'])
    except StopIteration:
        return None, ''


def get_area_peril_id_based_on_lonlat(record, areas):
    # Find minimum distance
    area = min(areas, key=lambda a: get_distance(record, a))
    
    # Return if min distance is greater than 15
    if get_distance(record, area) >= 15:
        return None, ''

    if record['country'] == area['arealevel_1']:
        return area['areaperil_id'], 'Mapped by Lon/Lat! AreaPerild_ID:{0} Distance to VRG= {1:.14}'.format(area['areaperil_id'], get_distance(record, area))
    else:
        return None, "Given Lon/Lat is not in the Country! found AreaPeril_ID= {}".format(area['areaperil_id'])


def get_distance(record, area):
    long1, lat1 = record['longitude'], record['latitude']
    long2, lat2 = area['lon'], area['lat']

    sPhi, sTeta = math.radians(lat1), math.radians(long1)
    ePhi, eTeta = math.radians(lat2), math.radians(long2)

    sX = EARTH_RADIUS * math.cos(sPhi) * math.cos(sTeta)
    sY = EARTH_RADIUS * math.cos(sPhi) * math.sin(sTeta)
    sZ = EARTH_RADIUS * math.sin(sPhi)
    eX = EARTH_RADIUS * math.cos(ePhi) * math.cos(eTeta)
    eY = EARTH_RADIUS * math.cos(ePhi) * math.sin(eTeta)
    eZ = EARTH_RADIUS * math.sin(ePhi)

    lenghtxyz = math.sqrt((sX - eX)**2 + (sY - eY)**2 + (sZ - eZ)**2)
    return 2 * math.asin(lenghtxyz / 2 / EARTH_RADIUS) * EARTH_RADIUS

def fix_locations_by_dictionary(record, location_map):
    level_5_dic = location_map['AREA_LEVEL_5']
    if record['city']:
        for row in level_5_dic:
            if row['arealevel_names'].upper() == record['city'].upper():
                record['city'] = row['arealevel_mode_names'].upper()

    level_3_dic = location_map['AREA_LEVEL_2']
    if record['state']:
        for row in level_3_dic:
            if row['arealevel_names'].upper() == record['state'].upper():
                record['state'] = row['arealevel_mode_names'].upper()

    level_1_dic = location_map['AREA_LEVEL_1']
    if record['country']:
        for row in level_1_dic:
            if row['arealevel_names'].upper() == record['country'].upper():
                record['country'] = row['arealevel_mode_names'].upper()


def read_record(line):
    vals = [x.strip().upper() for x in line]
    vals.reverse()
    return {
        'item_id': to_int(vals.pop()),
        'accntnum': vals.pop().strip(),
        'locnum': to_int(vals.pop()),
        'city': vals.pop().strip(),
        'state': vals.pop().strip(),
        'latitude': to_float(vals.pop()),
        'longitude': to_float(vals.pop()),
        'addrmatch': to_int(vals.pop()),
        'country': vals.pop().strip(),
        'numbldgs': to_int(vals.pop()),
        'bldgscheme': vals.pop().strip(),
        'bldgclass': vals.pop().strip(),
        'occscheme': vals.pop().strip(),
        'occtype': to_int(vals.pop()),
        'cntryscheme': vals.pop().strip(),
        'cntrycode': vals.pop().strip(),
        'eqcv1val': to_float(vals.pop()),
        'eqcv2val': to_float(vals.pop()),
        'locfilerowlocator': to_int(vals.pop())
    }

def read_location_mapping(filename):
    result = []
    with open(filename) as reader:
        reader.readline()
        for line in reader:
            vals = line.split(',')
            vals.reverse()
            result.append({
                'arealevel_names': vals.pop().strip(),
                'country_key': vals.pop().strip(),
                'arealevel_mode_names': vals.pop().strip()
            })
    return result

def read_vu_mapping(filename):
    result = []
    with open(filename) as reader:
        reader.readline()
        for line in reader:
            vals = line.split(',')
            vals.reverse()
            try:
                result.append({
                    'code': to_int(vals.pop()),
                    'risk_code': vals.pop().strip(),
                    'quality_code': vals.pop().strip()
                })
            except TypeError:
                pass
    return result

def read_construction_class(filename):
    result = []
    with open(filename) as reader:
        reader.readline()
        for line in reader:
            vals = line.split(',')
            vals.reverse()
            result.append({
                'class': vals.pop().strip(),
                'structural_type': vals.pop().strip(),
                'structural_height': vals.pop().strip(),
                'quality_code': vals.pop().strip()
            })
    return result


def read_vulnerabilities(filename):
    result = []
    with open(filename) as reader:
        reader.readline()
        for line in reader:
            vals = [x.strip().upper() for x in line.split(',') if x]
            vals.reverse()
            result.append({
                'id': to_int(vals.pop()),
                'code': vals.pop().strip()
            })
    return result


def read_areas(filename):
    result = []
    with open(filename) as reader:
        reader.readline()
        for line in reader:
            vals = [x.strip().upper() for x in line.split(',') if x]
            vals.reverse()
            result.append({
                'areaperil_id': to_int(vals.pop()),
                'area_id': to_int(vals.pop()),
                'lon': to_float(vals.pop()),
                'lat': to_float(vals.pop()),
                'population': to_float(vals.pop()),
                'arealevel_0': vals.pop().strip(),
                'arealevel_1': vals.pop().strip(),
                'arealevel_2': vals.pop().strip(),
                'arealevel_3': vals.pop().strip(),
                'arealevel_4': vals.pop().strip(),
                'arealevel_5': vals.pop().strip(),
                'aggregation_level': vals.pop().strip(),
            })
    return result

def read_location_mappings(data_directory):
    result = {}
    for i in range(1, 6):
        key = 'AREA_LEVEL_%d' % i
        values = []
        filename = 'LocationMapping_%s.csv' % key
        filenamepath = os.path.join(data_directory, filename)
        if os.path.isfile(filenamepath):
            values = read_location_mapping(filenamepath)
        result[key] = values
    return result


def read_vulnerability_mappings(data_directory):
    result = {}
    for key in ["ATC", "SIC", "IFM", "RMS IND"]:
        values = []
        filename = '%s OCCUPANCY SCHEME.csv' % key
        filenamepath = os.path.join(data_directory, filename)
        if os.path.isfile(filenamepath):
            values = read_vu_mapping(filenamepath)
        result[key] = values
    return result


def read_construction_classes(data_directory):
    result = {}
    for key in ["ATC", "ISO EQ", "RMS"]:
        values = []
        filename = '%s CONSTRUCTION CLASS.csv' % key
        filenamepath = os.path.join(data_directory, filename)
        if os.path.isfile(filenamepath):
            values = read_construction_class(filenamepath)
        result[key] = values
    return result


def get_vulnerability_id(record, dict_vulnerabilities, vul_mappings, construction_class):
    RISK_CODE = CATRISKS_CONTENTS_COVERAGE_CODE
    if record['occtype']:
        if record['occscheme'] in ['ATC', 'SIC', 'IFM']:
            vulnerabilities = vul_mappings[record['occscheme']]
            found_rec = [x for x in vulnerabilities if x['code'] == record['occtype']]
            if len(found_rec):
                RISK_CODE = found_rec[0]['risk_code']
        elif record['occscheme'] == "RMS IND":
            vulnerabilities = vul_mappings[record['occscheme']]
            found_rec = [x for x in vulnerabilities if x['code'] == record['occtype']]
            if len(found_rec):
                RISK_CODE = found_rec[0]['risk_code']
            else:
                vulnerabilities = vul_mappings['IFM']
                found_rec = [x for x in vulnerabilities if x['code'] == record['occtype']]
                if len(found_rec):
                    RISK_CODE = found_rec[0]['risk_code']

    structural_type, structural_height = 'XXX', 'XX'
    vulnerability_quality_code_1 = ''
    vulnerability_quality_code_2 = ''
    if record['bldgclass'] == '0':
        vulnerability_quality_code_1 = 'NO BUILDING CLASS'
    else:
        if record['bldgscheme'] in ['ATC', 'ISO EQ', 'RMS']:
            vulnerabilities = construction_class[record['occscheme']]
            found_rec = [x for x in vulnerabilities if x['class'] == record['bldgclass']]
            if len(found_rec):
                vulnerability_quality_code_1 = found_rec[0]['quality_code']
                structural_type = found_rec[0]['structural_type']
                structural_height = found_rec[0]['structural_height']
            else:
                vulnerability_quality_code_1 = 'NO BUILDING CLASS MATCH'
        else:
            vulnerability_quality_code_1 = 'NO BUILDING CLASS MATCH'
    if vulnerability_quality_code_1 in  ['NO BUILDING CLASS', 'NO BUILDING CLASS MATCH']:
        if record['occtype'] == 0:
            vulnerability_quality_code_2 = 'NO OCCUPANCY CLASS'
        else:
            if record['occscheme'] in ['ATC', 'SIC', 'IFM', 'RMS IND']:
                vulnerabilities = vul_mappings[record['occscheme']]
                found_rec = [x for x in vulnerabilities if x['code'] == record['occtype']]
                if len(found_rec):
                    vulnerability_quality_code_2 = found_rec[0]['quality_code']
                else:
                    vulnerability_quality_code_2 = 'NO BUILDING CLASS MATCH'
    else:
        vulnerability_quality_code_2 = vulnerability_quality_code_1

    QUALITY_CODE = 'MQU' if vulnerability_quality_code_2 == 'NO OCCUPANCY CLASS' else vulnerability_quality_code_2

    code = '%s-EQ-%s-%s-%s-%s-%s' % (record['country'], RISK_CODE, record['coverage_type'],
                                     structural_type, structural_height, QUALITY_CODE)
    result_records = [x for x in dict_vulnerabilities if x['code'] == code]
    if not len(result_records):
        return -1, '. There is no Vul-ID for %s' % code
    return result_records[0]['id'], ''


def get_tiv(record, records=None):
    if records is None:
        record['val1'] = record['eqcv1val'] if (record['eqcv1val'] and record['eqcv1val'] > 0) else record['eqcv2val']
    else:
        countif = len([r for r in records if (r['vulnerability_id'] == record['vulnerability_id'] and r['locfilerowlocator'] == record['locfilerowlocator'])])
        return float(record['tiv']) / countif


def set_coverage(records):
    row_locators = set([r['locfilerowlocator'] for r in records])
    for row_locator in row_locators:
        curr_records = [r for r in records if r['locfilerowlocator'] == row_locator]
        if len(curr_records) == 1:
            record = curr_records[0]
            if record['eqcv1val'] and record['eqcv1val']:
                record['coverage_type'] = CATRISKS_BUILDING_COVERAGE_CODE
            else:
                record['coverage_type'] = CATRISKS_CONTENTS_COVERAGE_CODE
        elif len(curr_records) == 2:
            curr_records[0]['coverage_type'] = CATRISKS_BUILDING_COVERAGE_CODE
            curr_records[-1]['coverage_type'] = CATRISKS_CONTENTS_COVERAGE_CODE
        else:
            raise Exception('Num_Loc_Row_Locator for LocFileRowLocator=%d more than 2' % row_locator)


def record_to_string(record):
    parts = (
        record['item_id'],
        record['areaperil_id'],
        record['vulnerability_id'],
        str(record['tiv']).rstrip('0').rstrip('.'),
        0,
        record['message']
    )
    return "{},{},{},{},{},{}".format(*parts)

def to_int(val):
    if val == 'n/a':
        return None
    return int(val)

def to_float(val):
    if not val or val == 'NULL':
        return None
    return float(val)
