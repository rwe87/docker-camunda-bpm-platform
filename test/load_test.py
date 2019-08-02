#!/usr/bin/env python3

#  Copyright 2019 InfAI (CC SES)
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import unittest
import threading
import requests
import time
import dateutil.parser
import os

HOST = 'localhost'
PORT = '8080'
BASE_URL = 'http://' + HOST + ':' + PORT + '/engine-rest'
PROCESS_MODEL_DIR = './resources'
PROCESS_INSTANCE_COUNT = 400  # number of instances per process model

process_definition_ids = []
process_instance_ids = []
durations = []
counter = 0


def start_instance(process_definition):
    try:
        response = requests.post(BASE_URL + '/process-definition/' + process_definition + '/start', json={})
        if response.status_code != 200:
            print('Process instance could not be started: {}'.format(process_definition))
        else:
            process_instance_ids.append(response.json()['id'])
            global counter
            counter += 1
    except Exception:
        print('Process instance could not be started: {}'.format(process_definition))

# get process instance history in order to calculate cycle times
def get_history(process_instance):
    try:
        response = requests.get(BASE_URL + '/history/process-instance/' + process_instance, timeout=120)
        if response.status_code != 200:
            print('Process instance history could not be retrieved: {}'.format(process_instance))
        else:
            start_time = dateutil.parser.parse(response.json()['startTime'])
            end_time = dateutil.parser.parse(response.json()['endTime'])

            duration = end_time - start_time
            durations.append(duration.total_seconds())
    except Exception:
        print('Process instance history could not be retrieved: {}'.format(process_instance))


class LoadTest(unittest.TestCase):

    def test_performance(self):
        print('Check if process engine is available...')
        response = requests.get(BASE_URL + '/engine')
        self.assertEqual(response.status_code, 200, 'Process engine is not available.')
        print('Process engine is available.')

        process_model_count = sum([len(files) for r, d, files in os.walk(PROCESS_MODEL_DIR)])
        print('Deploying {} process models...'.format(process_model_count))

        models = [f for f in os.listdir(PROCESS_MODEL_DIR) if
                  os.path.isfile(os.path.join(PROCESS_MODEL_DIR, f))]

        for model in models:
            file = open(PROCESS_MODEL_DIR + '/' + model, 'r')
            bpmn = file.read()
            file.close()

            files = {
                'deployment-name': model,
                'enable-duplicate-filtering': 'true',
                'deploy-changed-only': 'true',
                'deployment-source': 'senergy',
                'test.bpmn': bpmn
            }

            response = requests.post(BASE_URL + '/deployment/create', files=files)
            self.assertEqual(response.status_code, 200, 'Process could not be deployed: {}'.format(model))

            deployment_id = response.json()['id']
            response = requests.get(BASE_URL + '/process-definition?deploymentId=' + deployment_id)
            self.assertEqual(response.status_code, 200, 'DeploymentId could not be found: {}'.format(deployment_id))
            process_definition_ids.append(response.json()[0]['id'])

        print('Process models deployed.')

        print('Starting process instances...')

        threads = list()

        for process_definition in process_definition_ids:
            for i in range(PROCESS_INSTANCE_COUNT):
                x = threading.Thread(target=start_instance, args=(process_definition,))
                threads.append(x)

        start_time = time.time()

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        end_time = time.time()
        print('{} process instances started in {} seconds.'.format(counter, round(end_time - start_time, 3)))

        time.sleep(5)

        print('Retrieving process instance history...')

        threads = list()
        for process_instance in process_instance_ids:
            for i in range(PROCESS_INSTANCE_COUNT):
                get_history(process_instance)

        print('Process instance history retrieved.')

        duration_sum = 0
        for duration in durations:
            duration_sum += duration

        max_duration = max(durations)
        min_duration = min(durations)
        avg_duration = duration_sum / (len(process_instance_ids) * PROCESS_INSTANCE_COUNT)

        print('min: {}, max: {}, avg: {}'.format(min_duration, max_duration, float(avg_duration)))


if __name__ == '__main__':
    unittest.main()
