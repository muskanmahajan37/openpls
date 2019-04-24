#!/usr/bin/python3
# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from google.oauth2 import id_token
from google.auth.transport import requests
from google.auth import compute_engine
import json, os, re, uuid
import google.auth
from datetime import datetime, timedelta
from google.cloud import storage


def list_projects(request):

    # Set CORS headers for the preflight request
    if request.method == 'OPTIONS':
        # Allows GET requests from any origin with the Content-Type
        # header and caches preflight response for an 3600s
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': '*',
            'Access-Control-Allow-Headers': '*',
            'Access-Control-Max-Age': '3600',
            'Access-Control-Allow-Credentials': 'true'
        }
        return '', 204, headers

    client_id = os.getenv("OAUTH_CLIENT_ID")
    token = request.headers['Authorization'].split(' ').pop()
    auth_request = requests.Request()
    id_info = id_token.verify_oauth2_token(token, auth_request, client_id)
    if not id_info:
        return 'Unauthorized', 401

    # Set CORS headers for the main request
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Content-Type': 'text/json'
    }

    credentials, project = google.auth.default()
    storage_client = storage.Client(project, credentials)
    data_bucket = storage_client.lookup_bucket(os.getenv("DATA_BUCKET"))
    if data_bucket is None:
        return "Couldn't find data bucket " + os.getenv("DATA_BUCKET"), 500
    index_blob = data_bucket.blob(id_info["sub"] + "/index.json")
    try:
        index = json.loads(index_blob.download_as_string())
    except:
        index = {}

    contents = data_bucket.list_blobs(prefix=id_info["sub"])

    dir_re = re.compile('[^/]*/([^/]*)/.*csv')
    projects = []
    tzoffset_mins = int(request.headers["X-Timezone-Offset"]) if "X-Timezone-Offset" in request.headers else 0
    for blob in contents:
        re_result = dir_re.match(blob.name)
        if re_result:
            entry = {}
            created_tz = blob.time_created - timedelta(minutes=tzoffset_mins)
            entry["created"] = created_tz.strftime("%d %b %Y %I:%M%p")
            entry["id"] = re_result.group(1)
            entry["name"] = index[entry["id"]] if entry["id"] in index else ""
            projects.append(entry)

    new_project_uuid = str(uuid.uuid4())
    new_project_path = data_bucket.blob(
        id_info["sub"] + "/" + new_project_uuid + "/" + "data.csv")
    signed_url = new_project_path.create_resumable_upload_session(origin=request.headers["origin"])

    output = {
        "projects": projects,
        "new_project_upload_url": signed_url,
        "new_project_uuid": new_project_uuid
    }

    return json.dumps(output), 200, headers
