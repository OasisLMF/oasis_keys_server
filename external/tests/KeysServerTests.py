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

import csv
import io
import json
import os
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

        TEST_CONFIG = load_ini_file('KeysServerTests.ini')

        with io.open(os.path.abspath(TEST_CONFIG['MODEL_VERSION_FILE_PATH']), 'r', encoding='utf-8') as f:
            self.supplier_id, self.model_id, self.model_version = map(lambda s: s.strip(), map(tuple, csv.reader(f))[0])

        self.keys_server_hostname_or_ip = TEST_CONFIG['KEYS_SERVER_HOSTNAME_OR_IP']

        self.keys_server_port = TEST_CONFIG['KEYS_SERVER_PORT']

        self.keys_server_baseurl = 'http://{}:{}/{}/{}/{}'.format(
                                        self.keys_server_hostname_or_ip,
                                        self.keys_server_port,
                                        self.supplier_id,
                                        self.model_id,
                                        self.model_version
                                    )

        self.sample_csv_model_exposures_file_path = os.path.abspath(TEST_CONFIG['SAMPLE_CSV_MODEL_EXPOSURES_FILE_PATH'])
        self.sample_json_model_exposures_file_path = os.path.abspath(TEST_CONFIG['SAMPLE_JSON_MODEL_EXPOSURES_FILE_PATH'])


    def test_healthcheck(self):

        healthcheck_url = '{}/healthcheck'.format(self.keys_server_baseurl)
        res = requests.get(healthcheck_url)

        # Check that the response has a 200 status code
        self.assertEqual(res.status_code, 200)

        # Check that the healthcheck returned the 'OK' string
        msg = res.content.strip()
        self.assertEqual(msg, 'OK')


    def test_keys_request_csv(self):

        data = None
        with io.open(self.sample_csv_model_exposures_file_path, 'r', encoding='utf-8') as f:
            data = f.read().decode()

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
            self.assertEquals(set(result_dict.keys()), {'status', 'items'})

            self.assertIn(type(result_dict['status']), [str, unicode])

            self.assertEquals(result_dict['status'].lower(), 'success')

            self.assertEquals(type(result_dict['items']), list)

            items = result_dict['items']

            successes = [it for it in items if it['status'].lower() == 'success']
            failures = [it for it in items if it['status'].lower() != 'success']

            successful_lookup_record_keys = {'id', 'peril_id', 'coverage_type', 'area_peril_id', 'vulnerability_id', 'status', 'message'}
            failed_lookup_record_keys = {'id', 'peril_id', 'coverage_type', 'status', 'message'}

            if successes:
                self.assertEquals(
                    all(
                         type(r) == dict and successful_lookup_record_keys <= set(r.keys()) for r in successes
                    ),
                    True
                )

            if failures:
                self.assertEquals(
                    all(
                        type(r) == dict and failed_lookup_record_keys <= set(r.keys()) for r in failures
                    ),
                    True
                )

    def test_keys_request_csv__invalid_content_type(self):

        data = None
        with io.open(self.sample_csv_model_exposures_file_path, 'r', encoding='utf-8') as f:
            data = f.read().decode()

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

        data = None
        with io.open(self.sample_json_model_exposures_file_path, 'r', encoding='utf-8') as f:
            data = f.read().decode()

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
            self.assertEquals(set(result_dict.keys()), {'status', 'items'})

            self.assertIn(type(result_dict['status']), [str, unicode])

            self.assertEquals(result_dict['status'].lower(), 'success')

            self.assertEquals(type(result_dict['items']), list)

            items = result_dict['items']

            successes = [it for it in items if it['status'].lower() == 'success']

            failures = [it for it in items if it['status'].lower() != 'success']

            successful_lookup_record_keys = {'id', 'peril_id', 'coverage_type', 'area_peril_id', 'vulnerability_id', 'status', 'message'}
            failed_lookup_record_keys = {'id', 'peril_id', 'coverage_type', 'status', 'message'}

            if successes:
                self.assertEquals(
                    all(
                         type(r) == dict and set(successful_lookup_record_keys) <= set(r.keys()) for r in successes
                    ),
                    True
                )

            if failures:
                self.assertEquals(
                    all(
                        type(r) == dict and set(failed_lookup_record_keys) <= set(r.keys()) for r in failures
                    ),
                    True
                )


    def test_keys_request_json__invalid_content_type(self):

        data = None
        with io.open(self.sample_json_model_exposures_file_path, 'r', encoding='utf-8') as f:
            data = f.read().decode()

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