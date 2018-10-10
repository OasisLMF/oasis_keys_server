from __future__ import print_function

# -*- coding: utf-8 -*-

"""
Integration tests for a model keys server.
"""

# BSD 3-Clause License
#
# Copyright (c) 2017-2020, Oasis Loss Modelling Framework
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import io
import json
import os
import six
import sys
import unittest

import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.getcwd(), os.pardir, os.pardir)))

from oasislmf.utils.exceptions import OasisException
from oasislmf.utils.conf import load_ini_file
from oasislmf.utils.http import (
    HTTP_REQUEST_CONTENT_TYPE_CSV,
    HTTP_REQUEST_CONTENT_TYPE_JSON,
)


class KeysServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(self):

        # Required config settings
        TEST_CONFIG = load_ini_file('KeysServerTests.ini')
        with io.open(os.path.abspath(TEST_CONFIG['MODEL_VERSION_FILE_PATH']), 'r', encoding='utf-8') as f:
            self.supplier_id, self.model_id, self.model_version = f.read().strip().split(',')
        self.keys_server_hostname_or_ip = TEST_CONFIG['KEYS_SERVER_HOSTNAME_OR_IP']
        self.keys_server_port = TEST_CONFIG['KEYS_SERVER_PORT']
        self.keys_server_baseurl = 'http://{}:{}/{}/{}/{}'.format(
                                        self.keys_server_hostname_or_ip,
                                        self.keys_server_port,
                                        self.supplier_id,
                                        self.model_id,
                                        self.model_version
                                    )
        # Optional config settings
        path_modelloc_csv  = TEST_CONFIG.get('SAMPLE_CSV_MODEL_EXPOSURES_FILE_PATH')
        path_modelloc_json = TEST_CONFIG.get('SAMPLE_JSON_MODEL_EXPOSURES_FILE_PATH')
        path_output_dir    = TEST_CONFIG.get('OUTPUT_FILE_DIR')
        self.skip_invalid  = TEST_CONFIG.get('SKIP_INVALID_TESTS')
        self.model_exposures_csv  = os.path.abspath(path_modelloc_csv) if path_modelloc_csv else None
        self.model_exposures_json = os.path.abspath(path_modelloc_json) if path_modelloc_json else None
        self.store_output_dir     = os.path.abspath(path_output_dir) if path_output_dir else None

    def test_healthcheck(self):
        healthcheck_url = '{}/healthcheck'.format(self.keys_server_baseurl)

        # Check that the response has a 200 status code
        res = requests.get(healthcheck_url)
        self.assertEqual(res.status_code, 200)

        # Check that the healthcheck returned the 'OK' string
        msg = res.content.strip().decode()
        self.assertEqual(msg, 'OK')


    def test_keys_request_csv(self):
        if not self.model_exposures_csv:
            self.skipTest("CSV exposure file path not given")

        data = None
        with io.open(self.model_exposures_csv, 'r', encoding='utf-8') as f:
            data = u'{}'.format(f.read().strip())

        headers = {
            'Accept-Encoding': 'identity,deflate,gzip,compress',
            'Content-Type': HTTP_REQUEST_CONTENT_TYPE_CSV,
            'Content-Length': str(len(data))
        }

        get_keys_url = '{}/get_keys'.format(self.keys_server_baseurl)
        res = requests.post(get_keys_url, headers=headers, data=data)

        # Check that the response has a 200 status code
        self.assertEqual(res.status_code, 200)

        # Check that the response content is valid JSON and has valid content.
        result_dict = None
        try:
            result_dict = json.loads(res.content)
        except ValueError:
            self.assertIsNotNone(result_dict)
        else:
            self.assertEqual(set(result_dict.keys()), {'status', 'items'})
            self.assertTrue(isinstance(result_dict['status'], six.string_types))
            self.assertEqual(result_dict['status'].lower(), 'success')
            self.assertEqual(type(result_dict['items']), list)
            items = result_dict['items']

            successes = [it for it in items if it['status'].lower() == 'success']
            failures = [it for it in items if it['status'].lower() != 'success']

            successful_lookup_record_keys = {'id', 'peril_id', 'coverage_type', 'area_peril_id', 'vulnerability_id', 'status', 'message'}
            failed_lookup_record_keys = {'id', 'peril_id', 'coverage_type', 'status', 'message'}

            # Check that result dict keys are valid
            if successes:
                successes_valid = all(type(r) == dict and successful_lookup_record_keys <= set(r.keys()) for r in successes)
                self.assertEqual(successes_valid, True)
            if failures:
                failures_valid = all(type(r) == dict and failed_lookup_record_keys <= set(r.keys()) for r in failures)
                self.assertEqual(failures_valid, True)

            # Store result dict for inspection 
            if self.store_output_dir:
                file_name = 'request_csv_result.json'
                with io.open(os.path.join(self.store_output_dir, file_name) , 'w', encoding='utf-8') as f:
                    f.write(json.dumps(result_dict))
                


    def test_keys_request_csv__invalid_content_type(self):
        if self.skip_invalid:
            self.skipTest("Skip invalid flag set")

        data = None
        with io.open(self.model_exposures_csv, 'r', encoding='utf-8') as f:
            data = u'{}'.format(f.read().strip())

        # test for unrecognised content type header
        headers = {
            'Accept-Encoding': 'identity,deflate,gzip,compress',
            'Content-Type': 'text/html; charset=utf-8',
            'Content-Length': str(len(data))
        }

        get_keys_url = '{}/get_keys'.format(self.keys_server_baseurl)
        res = requests.post(get_keys_url, headers=headers, data=data)

        # Check that the response does not have a 200 status code
        self.assertNotEqual(res.status_code, 200)

        # test for missing content type header
        headers = {
            'Accept-Encoding': 'identity,deflate,gzip,compress',
            'Content-Length': str(len(data))
        }

        get_keys_url = '{}/get_keys'.format(self.keys_server_baseurl)
        res = requests.post(get_keys_url, headers=headers, data=data)

        # Check that the response does not have a 200 status code
        self.assertNotEqual(res.status_code, 200)


    def test_keys_request_json(self):
        if not self.model_exposures_json:
            self.skipTest("JSON exposure file path not given")

        data = None
        with io.open(self.model_exposures_json, 'r', encoding='utf-8') as f:
            data = u'{}'.format(f.read().strip())

        headers = {
            'Accept-Encoding': 'identity,deflate,gzip,compress',
            'Content-Type': HTTP_REQUEST_CONTENT_TYPE_JSON,
            'Content-Length': str(len(data))
        }

        get_keys_url = '{}/get_keys'.format(self.keys_server_baseurl)
        res = requests.post(get_keys_url, headers=headers, data=data)

        # Check that the response has a 200 status code
        self.assertEqual(res.status_code, 200)

        # Check that the response content is valid JSON and has valid content.
        result_dict = None
        try:
            result_dict = json.loads(res.content)
        except ValueError:
            self.assertIsNotNone(result_dict)
        else:
            self.assertEqual(set(result_dict.keys()), {'status', 'items'})
            self.assertTrue(isinstance(result_dict['status'], six.string_types))
            self.assertEqual(result_dict['status'].lower(), 'success')
            self.assertEqual(type(result_dict['items']), list)

            items = result_dict['items']
            successes = [it for it in items if it['status'].lower() == 'success']
            failures = [it for it in items if it['status'].lower() != 'success']
            successful_lookup_record_keys = {'id', 'peril_id', 'coverage_type', 'area_peril_id', 'vulnerability_id', 'status', 'message'}
            failed_lookup_record_keys = {'id', 'peril_id', 'coverage_type', 'status', 'message'}

            # Check that result dict keys are valid
            if successes:
                successes_valid = all(type(r) == dict and successful_lookup_record_keys <= set(r.keys()) for r in successes)
                self.assertEqual(successes_valid, True)
            if failures:
                failures_valid = all(type(r) == dict and failed_lookup_record_keys <= set(r.keys()) for r in failures)
                self.assertEqual(failures_valid, True)

            # Store result dict for inspection 
            if self.store_output_dir:
                file_name = 'request_json_result.json'
                with io.open(os.path.join(self.store_output_dir, file_name) , 'w', encoding='utf-8') as f:
                    f.write(json.dumps(result_dict))


    def test_keys_request_json__invalid_content_type(self):
        if self.skip_invalid:
            self.skipTest("Skip invalid flag set")

        data = None
        with io.open(self.model_exposures_json, 'r', encoding='utf-8') as f:
            data = u'{}'.format(f.read().strip())

        # test for unrecognised content type header
        headers = {
            'Accept-Encoding': 'identity,deflate,gzip,compress',
            'Content-Type': 'text/html; charset=utf-8',
            'Content-Length': str(len(data))
        }

        get_keys_url = '{}/get_keys'.format(self.keys_server_baseurl)
        res = requests.post(get_keys_url, headers=headers, data=data)

        # Check that the response does not have a 200 status code
        self.assertNotEqual(res.status_code, 200)

        # test for missing content type header
        headers = {
            'Accept-Encoding': 'identity,deflate,gzip,compress',
            'Content-Length': str(len(data))
        }

        get_keys_url = '{}/get_keys'.format(self.keys_server_baseurl)
        res = requests.post(get_keys_url, headers=headers, data=data)

        # Check that the response does not have a 200 status code
        self.assertNotEqual(res.status_code, 200)


if __name__ == '__main__':
    unittest.main()
