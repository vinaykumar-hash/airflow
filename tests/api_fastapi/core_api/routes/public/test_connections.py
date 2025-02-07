# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
from __future__ import annotations

import os
from unittest import mock

import pytest

from airflow.models import Connection
from airflow.secrets.environment_variables import CONN_ENV_PREFIX
from airflow.utils.session import provide_session

from tests_common.test_utils.db import clear_db_connections

pytestmark = pytest.mark.db_test

TEST_CONN_ID = "test_connection_id"
TEST_CONN_TYPE = "test_type"
TEST_CONN_DESCRIPTION = "some_description_a"
TEST_CONN_HOST = "some_host_a"
TEST_CONN_PORT = 8080
TEST_CONN_LOGIN = "some_login"


TEST_CONN_ID_2 = "test_connection_id_2"
TEST_CONN_TYPE_2 = "test_type_2"
TEST_CONN_DESCRIPTION_2 = "some_description_b"
TEST_CONN_HOST_2 = "some_host_b"
TEST_CONN_PORT_2 = 8081
TEST_CONN_LOGIN_2 = "some_login_b"


TEST_CONN_ID_3 = "test_connection_id_3"
TEST_CONN_TYPE_3 = "test_type_3"


@provide_session
def _create_connection(session) -> None:
    connection_model = Connection(
        conn_id=TEST_CONN_ID,
        conn_type=TEST_CONN_TYPE,
        description=TEST_CONN_DESCRIPTION,
        host=TEST_CONN_HOST,
        port=TEST_CONN_PORT,
        login=TEST_CONN_LOGIN,
    )
    session.add(connection_model)


@provide_session
def _create_connections(session) -> None:
    _create_connection(session)
    connection_model_2 = Connection(
        conn_id=TEST_CONN_ID_2,
        conn_type=TEST_CONN_TYPE_2,
        description=TEST_CONN_DESCRIPTION_2,
        host=TEST_CONN_HOST_2,
        port=TEST_CONN_PORT_2,
        login=TEST_CONN_LOGIN_2,
    )
    session.add(connection_model_2)


class TestConnectionEndpoint:
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        clear_db_connections(False)

    def teardown_method(self) -> None:
        clear_db_connections()

    def create_connection(self):
        _create_connection()

    def create_connections(self):
        _create_connections()


class TestDeleteConnection(TestConnectionEndpoint):
    def test_delete_should_respond_204(self, test_client, session):
        self.create_connection()
        conns = session.query(Connection).all()
        assert len(conns) == 1
        response = test_client.delete(f"/public/connections/{TEST_CONN_ID}")
        assert response.status_code == 204
        connection = session.query(Connection).all()
        assert len(connection) == 0

    def test_delete_should_respond_404(self, test_client):
        response = test_client.delete(f"/public/connections/{TEST_CONN_ID}")
        assert response.status_code == 404
        body = response.json()
        assert f"The Connection with connection_id: `{TEST_CONN_ID}` was not found" == body["detail"]


class TestGetConnection(TestConnectionEndpoint):
    def test_get_should_respond_200(self, test_client, session):
        self.create_connection()
        response = test_client.get(f"/public/connections/{TEST_CONN_ID}")
        assert response.status_code == 200
        body = response.json()
        assert body["connection_id"] == TEST_CONN_ID
        assert body["conn_type"] == TEST_CONN_TYPE

    def test_get_should_respond_404(self, test_client):
        response = test_client.get(f"/public/connections/{TEST_CONN_ID}")
        assert response.status_code == 404
        body = response.json()
        assert f"The Connection with connection_id: `{TEST_CONN_ID}` was not found" == body["detail"]

    def test_get_should_respond_200_with_extra(self, test_client, session):
        self.create_connection()
        connection = session.query(Connection).first()
        connection.extra = '{"extra_key": "extra_value"}'
        session.commit()
        response = test_client.get(f"/public/connections/{TEST_CONN_ID}")
        assert response.status_code == 200
        body = response.json()
        assert body["connection_id"] == TEST_CONN_ID
        assert body["conn_type"] == TEST_CONN_TYPE
        assert body["extra"] == '{"extra_key": "extra_value"}'

    @pytest.mark.enable_redact
    def test_get_should_respond_200_with_extra_redacted(self, test_client, session):
        self.create_connection()
        connection = session.query(Connection).first()
        connection.extra = '{"password": "test-password"}'
        session.commit()
        response = test_client.get(f"/public/connections/{TEST_CONN_ID}")
        assert response.status_code == 200
        body = response.json()
        assert body["connection_id"] == TEST_CONN_ID
        assert body["conn_type"] == TEST_CONN_TYPE
        assert body["extra"] == '{"password": "***"}'


class TestGetConnections(TestConnectionEndpoint):
    @pytest.mark.parametrize(
        "query_params, expected_total_entries, expected_ids",
        [
            # Filters
            ({}, 2, [TEST_CONN_ID, TEST_CONN_ID_2]),
            ({"limit": 1}, 2, [TEST_CONN_ID]),
            ({"limit": 1, "offset": 1}, 2, [TEST_CONN_ID_2]),
            # Sort
            ({"order_by": "-connection_id"}, 2, [TEST_CONN_ID_2, TEST_CONN_ID]),
            ({"order_by": "conn_type"}, 2, [TEST_CONN_ID, TEST_CONN_ID_2]),
            ({"order_by": "-conn_type"}, 2, [TEST_CONN_ID_2, TEST_CONN_ID]),
            ({"order_by": "description"}, 2, [TEST_CONN_ID, TEST_CONN_ID_2]),
            ({"order_by": "-description"}, 2, [TEST_CONN_ID_2, TEST_CONN_ID]),
            ({"order_by": "host"}, 2, [TEST_CONN_ID, TEST_CONN_ID_2]),
            ({"order_by": "-host"}, 2, [TEST_CONN_ID_2, TEST_CONN_ID]),
            ({"order_by": "port"}, 2, [TEST_CONN_ID, TEST_CONN_ID_2]),
            ({"order_by": "-port"}, 2, [TEST_CONN_ID_2, TEST_CONN_ID]),
            ({"order_by": "id"}, 2, [TEST_CONN_ID, TEST_CONN_ID_2]),
            ({"order_by": "-id"}, 2, [TEST_CONN_ID_2, TEST_CONN_ID]),
        ],
    )
    def test_should_respond_200(
        self, test_client, session, query_params, expected_total_entries, expected_ids
    ):
        self.create_connections()
        response = test_client.get("/public/connections", params=query_params)
        assert response.status_code == 200

        body = response.json()
        assert body["total_entries"] == expected_total_entries
        assert [connection["connection_id"] for connection in body["connections"]] == expected_ids


class TestPostConnection(TestConnectionEndpoint):
    @pytest.mark.parametrize(
        "body",
        [
            {"connection_id": TEST_CONN_ID, "conn_type": TEST_CONN_TYPE},
            {"connection_id": TEST_CONN_ID, "conn_type": TEST_CONN_TYPE, "extra": None},
            {"connection_id": TEST_CONN_ID, "conn_type": TEST_CONN_TYPE, "extra": "{}"},
            {"connection_id": TEST_CONN_ID, "conn_type": TEST_CONN_TYPE, "extra": '{"key": "value"}'},
            {
                "connection_id": TEST_CONN_ID,
                "conn_type": TEST_CONN_TYPE,
                "description": "test_description",
                "host": "test_host",
                "login": "test_login",
                "schema": "test_schema",
                "port": 8080,
                "extra": '{"key": "value"}',
            },
        ],
    )
    def test_post_should_respond_201(self, test_client, session, body):
        response = test_client.post("/public/connections", json=body)
        assert response.status_code == 201
        connection = session.query(Connection).all()
        assert len(connection) == 1

    @pytest.mark.parametrize(
        "body",
        [
            {"connection_id": "****", "conn_type": TEST_CONN_TYPE},
            {"connection_id": "test()", "conn_type": TEST_CONN_TYPE},
            {"connection_id": "this_^$#is_invalid", "conn_type": TEST_CONN_TYPE},
            {"connection_id": "iam_not@#$_connection_id", "conn_type": TEST_CONN_TYPE},
        ],
    )
    def test_post_should_respond_422_for_invalid_conn_id(self, test_client, body):
        response = test_client.post("/public/connections", json=body)
        assert response.status_code == 422
        # This regex is used for validation in ConnectionBody
        assert response.json() == {
            "detail": [
                {
                    "ctx": {"pattern": r"^[\w.-]+$"},
                    "input": f"{body['connection_id']}",
                    "loc": ["body", "connection_id"],
                    "msg": "String should match pattern '^[\\w.-]+$'",
                    "type": "string_pattern_mismatch",
                }
            ]
        }

    @pytest.mark.parametrize(
        "body",
        [
            {"connection_id": TEST_CONN_ID, "conn_type": TEST_CONN_TYPE},
        ],
    )
    def test_post_should_respond_already_exist(self, test_client, body):
        response = test_client.post("/public/connections", json=body)
        assert response.status_code == 201
        # Another request
        response = test_client.post("/public/connections", json=body)
        assert response.status_code == 409
        response_json = response.json()
        assert "detail" in response_json
        assert list(response_json["detail"].keys()) == ["reason", "statement", "orig_error"]

    @pytest.mark.enable_redact
    @pytest.mark.parametrize(
        "body, expected_response",
        [
            (
                {"connection_id": TEST_CONN_ID, "conn_type": TEST_CONN_TYPE, "password": "test-password"},
                {
                    "connection_id": TEST_CONN_ID,
                    "conn_type": TEST_CONN_TYPE,
                    "description": None,
                    "extra": None,
                    "host": None,
                    "login": None,
                    "password": "***",
                    "port": None,
                    "schema": None,
                },
            ),
            (
                {"connection_id": TEST_CONN_ID, "conn_type": TEST_CONN_TYPE, "password": "?>@#+!_%()#"},
                {
                    "connection_id": TEST_CONN_ID,
                    "conn_type": TEST_CONN_TYPE,
                    "description": None,
                    "extra": None,
                    "host": None,
                    "login": None,
                    "password": "***",
                    "port": None,
                    "schema": None,
                },
            ),
            (
                {
                    "connection_id": TEST_CONN_ID,
                    "conn_type": TEST_CONN_TYPE,
                    "password": "A!rF|0wi$aw3s0m3",
                    "extra": '{"password": "test-password"}',
                },
                {
                    "connection_id": TEST_CONN_ID,
                    "conn_type": TEST_CONN_TYPE,
                    "description": None,
                    "extra": '{"password": "***"}',
                    "host": None,
                    "login": None,
                    "password": "***",
                    "port": None,
                    "schema": None,
                },
            ),
        ],
    )
    def test_post_should_response_201_redacted_password(self, test_client, body, expected_response):
        response = test_client.post("/public/connections", json=body)
        assert response.status_code == 201
        assert response.json() == expected_response


class TestPutConnections(TestConnectionEndpoint):
    @pytest.mark.parametrize(
        "body",
        [
            {
                "connections": [
                    {"connection_id": TEST_CONN_ID, "conn_type": TEST_CONN_TYPE},
                    {"connection_id": TEST_CONN_ID_2, "conn_type": TEST_CONN_TYPE_2, "extra": None},
                ]
            },
            {
                "connections": [
                    {"connection_id": TEST_CONN_ID, "conn_type": TEST_CONN_TYPE, "extra": "{}"},
                    {
                        "connection_id": TEST_CONN_ID_2,
                        "conn_type": TEST_CONN_TYPE_2,
                        "extra": '{"key": "value"}',
                    },
                    {
                        "connection_id": TEST_CONN_ID_3,
                        "conn_type": TEST_CONN_ID_3,
                        "description": "test_description",
                        "host": "test_host",
                        "login": "test_login",
                        "schema": "test_schema",
                        "port": 8080,
                        "extra": '{"key": "value"}',
                    },
                ]
            },
        ],
    )
    def test_put_should_respond_201(self, test_client, session, body):
        response = test_client.put("/public/connections/bulk", json=body)
        assert response.status_code == 201
        connection = session.query(Connection).all()
        assert len(connection) == len(body["connections"])

    @pytest.mark.parametrize(
        "first_request_body, first_expected_entries_count, second_request_body, second_expected_entries_count, second_request_expected_response",
        [
            pytest.param(
                {
                    "connections": [
                        {"connection_id": TEST_CONN_ID, "conn_type": TEST_CONN_TYPE},
                        {"connection_id": TEST_CONN_ID_2, "conn_type": TEST_CONN_TYPE_2, "extra": None},
                    ]
                },
                2,
                {
                    "connections": [
                        {"connection_id": TEST_CONN_ID, "conn_type": f"new_{TEST_CONN_TYPE}"},
                        {
                            "connection_id": TEST_CONN_ID_3,
                            "conn_type": TEST_CONN_TYPE_3,
                            "port": 8080,
                            "schema": "test_schema",
                        },
                    ],
                    "overwrite": True,
                },
                3,
                {
                    "connections": [
                        {
                            "connection_id": TEST_CONN_ID,
                            "conn_type": f"new_{TEST_CONN_TYPE}",
                            "description": None,
                            "extra": None,
                            "host": None,
                            "login": None,
                            "password": None,
                            "port": None,
                            "schema": None,
                        },
                        {
                            "connection_id": TEST_CONN_ID_3,
                            "conn_type": TEST_CONN_TYPE_3,
                            "description": None,
                            "extra": None,
                            "host": None,
                            "login": None,
                            "password": None,
                            "port": 8080,
                            "schema": "test_schema",
                        },
                    ],
                    "total_entries": 2,
                },
                id="overwrite_with_partial_existing_request_body",
            ),
            pytest.param(
                {
                    "connections": [
                        {"connection_id": TEST_CONN_ID, "conn_type": TEST_CONN_TYPE, "extra": "{}"},
                        {
                            "connection_id": TEST_CONN_ID_2,
                            "conn_type": TEST_CONN_TYPE_2,
                            "extra": '{"key": "value"}',
                        },
                        {
                            "connection_id": TEST_CONN_ID_3,
                            "conn_type": TEST_CONN_ID_3,
                            "description": "test_description",
                            "host": "test_host",
                            "login": "test_login",
                            "schema": "test_schema",
                            "port": 8080,
                            "extra": '{"key": "value"}',
                        },
                    ]
                },
                3,
                {
                    "connections": [
                        {"connection_id": TEST_CONN_ID, "conn_type": f"new_{TEST_CONN_TYPE}", "extra": "{}"},
                        {
                            "connection_id": TEST_CONN_ID_2,
                            "conn_type": f"new_{TEST_CONN_TYPE_2}",
                            "extra": '{"key": "new_value"}',
                        },
                        {
                            "connection_id": TEST_CONN_ID_3,
                            "conn_type": TEST_CONN_ID_3,
                            "description": "new_test_description",
                            "host": "new_test_host",
                            "login": "new_test_login",
                            "schema": "new_test_schema",
                            "port": 28080,
                            "extra": '{"key": "new_value"}',
                        },
                    ],
                    "overwrite": True,
                },
                3,
                {
                    "connections": [
                        {
                            "connection_id": TEST_CONN_ID,
                            "conn_type": f"new_{TEST_CONN_TYPE}",
                            "description": None,
                            "extra": "{}",
                            "host": None,
                            "login": None,
                            "password": None,
                            "port": None,
                            "schema": None,
                        },
                        {
                            "connection_id": TEST_CONN_ID_2,
                            "conn_type": f"new_{TEST_CONN_TYPE_2}",
                            "description": None,
                            "extra": '{"key": "new_value"}',
                            "host": None,
                            "login": None,
                            "password": None,
                            "port": None,
                            "schema": None,
                        },
                        {
                            "connection_id": TEST_CONN_ID_3,
                            "conn_type": TEST_CONN_ID_3,
                            "description": "new_test_description",
                            "host": "new_test_host",
                            "login": "new_test_login",
                            "password": None,
                            "schema": "new_test_schema",
                            "port": 28080,
                            "extra": '{"key": "new_value"}',
                        },
                    ],
                    "total_entries": 3,
                },
                id="overwrite_with_extra_request_body",
            ),
        ],
    )
    def test_put_should_respond_200_overwrite(
        self,
        test_client,
        session,
        first_request_body,
        first_expected_entries_count,
        second_request_body,
        second_expected_entries_count,
        second_request_expected_response,
    ):
        response = test_client.put("/public/connections/bulk", json=first_request_body)
        assert response.status_code == 201
        assert session.query(Connection).count() == first_expected_entries_count
        # Another request
        response = test_client.put("/public/connections/bulk", json=second_request_body)
        assert response.status_code == 200
        assert response.json() == second_request_expected_response
        assert session.query(Connection).count() == second_expected_entries_count

    @pytest.mark.parametrize(
        "body",
        [
            {
                "connections": [
                    {"connection_id": "****", "conn_type": TEST_CONN_TYPE},
                    {"connection_id": "test()", "conn_type": TEST_CONN_TYPE},
                ]
            },
            {
                "connections": [
                    {"connection_id": "this_^$#is_invalid", "conn_type": TEST_CONN_TYPE},
                    {"connection_id": "iam_not@#$_connection_id", "conn_type": TEST_CONN_TYPE},
                ]
            },
        ],
    )
    def test_put_should_respond_422_for_invalid_conn_id(self, test_client, body):
        response = test_client.put("/public/connections/bulk", json=body)
        assert response.status_code == 422
        expected_response_detail = [
            {
                "ctx": {"pattern": r"^[\w.-]+$"},
                "input": f"{body['connections'][conn_index]['connection_id']}",
                "loc": ["body", "connections", conn_index, "connection_id"],
                "msg": "String should match pattern '^[\\w.-]+$'",
                "type": "string_pattern_mismatch",
            }
            for conn_index in range(len(body["connections"]))
        ]
        assert response.json() == {"detail": expected_response_detail}

    @pytest.mark.parametrize(
        "body",
        [
            {
                "connections": [
                    {"connection_id": TEST_CONN_ID, "conn_type": TEST_CONN_TYPE},
                    {"connection_id": TEST_CONN_ID_2, "conn_type": TEST_CONN_TYPE_2, "extra": None},
                ]
            },
        ],
    )
    def test_put_should_respond_409_already_exist(self, test_client, body):
        response = test_client.put("/public/connections/bulk", json=body)
        assert response.status_code == 201
        # Another request
        response = test_client.put("/public/connections/bulk", json=body)
        assert response.status_code == 409
        response_json = response.json()
        assert "detail" in response_json
        assert list(response_json["detail"].keys()) == ["reason", "statement", "orig_error"]

    @pytest.mark.enable_redact
    @pytest.mark.parametrize(
        "body, expected_response",
        [
            (
                {
                    "connections": [
                        {
                            "connection_id": TEST_CONN_ID,
                            "conn_type": TEST_CONN_TYPE,
                            "password": "test-password",
                        },
                        {
                            "connection_id": TEST_CONN_ID_2,
                            "conn_type": TEST_CONN_TYPE_2,
                            "password": "?>@#+!_%()#",
                        },
                    ]
                },
                {
                    "connections": [
                        {
                            "connection_id": TEST_CONN_ID,
                            "conn_type": TEST_CONN_TYPE,
                            "description": None,
                            "extra": None,
                            "host": None,
                            "login": None,
                            "password": "***",
                            "port": None,
                            "schema": None,
                        },
                        {
                            "connection_id": TEST_CONN_ID_2,
                            "conn_type": TEST_CONN_TYPE_2,
                            "description": None,
                            "extra": None,
                            "host": None,
                            "login": None,
                            "password": "***",
                            "port": None,
                            "schema": None,
                        },
                    ],
                    "total_entries": 2,
                },
            ),
            (
                {
                    "connections": [
                        {
                            "connection_id": TEST_CONN_ID,
                            "conn_type": TEST_CONN_TYPE,
                            "password": "A!rF|0wi$aw3s0m3",
                            "extra": '{"password": "test-password"}',
                        }
                    ]
                },
                {
                    "connections": [
                        {
                            "connection_id": TEST_CONN_ID,
                            "conn_type": TEST_CONN_TYPE,
                            "description": None,
                            "extra": '{"password": "***"}',
                            "host": None,
                            "login": None,
                            "password": "***",
                            "port": None,
                            "schema": None,
                        },
                    ],
                    "total_entries": 1,
                },
            ),
        ],
    )
    def test_put_should_response_201_redacted_password(self, test_client, body, expected_response):
        response = test_client.put("/public/connections/bulk", json=body)
        assert response.status_code == 201
        assert response.json() == expected_response

    @pytest.mark.enable_redact
    @pytest.mark.parametrize(
        "body, expected_response",
        [
            pytest.param(
                {
                    "connections": [
                        {
                            "connection_id": TEST_CONN_ID,
                            "conn_type": TEST_CONN_TYPE_2,
                            "password": "new-test-password",
                            "description": "new-description",
                        },
                        {
                            "connection_id": TEST_CONN_ID_2,
                            "conn_type": TEST_CONN_TYPE,
                            "password": "new-?>@#+!_%()#",
                            "port": 80,
                        },
                    ],
                    "overwrite": True,
                },
                {
                    "connections": [
                        {
                            "connection_id": TEST_CONN_ID,
                            "conn_type": TEST_CONN_TYPE_2,
                            "description": "new-description",
                            "extra": None,
                            "host": None,
                            "login": None,
                            "password": "***",
                            "port": None,
                            "schema": None,
                        },
                        {
                            "connection_id": TEST_CONN_ID_2,
                            "conn_type": TEST_CONN_TYPE,
                            "description": None,
                            "extra": None,
                            "host": None,
                            "login": None,
                            "password": "***",
                            "port": 80,
                            "schema": None,
                        },
                    ],
                    "total_entries": 2,
                },
                id="redact_password_with_overwrite",
            ),
            pytest.param(
                {
                    "connections": [
                        {
                            "connection_id": TEST_CONN_ID,
                            "conn_type": TEST_CONN_TYPE,
                            "password": "A!rF|0wi$aw3s0m3",
                            "extra": '{"password": "test-password"}',
                        }
                    ],
                    "overwrite": True,
                },
                {
                    "connections": [
                        {
                            "connection_id": TEST_CONN_ID,
                            "conn_type": TEST_CONN_TYPE,
                            "description": None,
                            "extra": '{"password": "***"}',
                            "host": None,
                            "login": None,
                            "password": "***",
                            "port": None,
                            "schema": None,
                        },
                    ],
                    "total_entries": 1,
                },
                id="redact_extra_with_overwrite",
            ),
        ],
    )
    def test_put_should_response_200_redacted_password_with_overwrite(
        self, test_client, body, expected_response
    ):
        self.create_connections()
        response = test_client.put("/public/connections/bulk", json=body)
        assert response.status_code == 200
        assert response.json() == expected_response


class TestPatchConnection(TestConnectionEndpoint):
    @pytest.mark.parametrize(
        "body",
        [
            {"connection_id": TEST_CONN_ID, "conn_type": TEST_CONN_TYPE, "extra": '{"key": "var"}'},
            {"connection_id": TEST_CONN_ID, "conn_type": TEST_CONN_TYPE, "host": "test_host_patch"},
            {
                "connection_id": TEST_CONN_ID,
                "conn_type": TEST_CONN_TYPE,
                "host": "test_host_patch",
                "port": 80,
            },
            {"connection_id": TEST_CONN_ID, "conn_type": TEST_CONN_TYPE, "login": "test_login_patch"},
            {"connection_id": TEST_CONN_ID, "conn_type": TEST_CONN_TYPE, "port": 80},
            {
                "connection_id": TEST_CONN_ID,
                "conn_type": TEST_CONN_TYPE,
                "port": 80,
                "login": "test_login_patch",
            },
        ],
    )
    @provide_session
    def test_patch_should_respond_200(self, test_client, body, session):
        self.create_connection()

        response = test_client.patch(f"/public/connections/{TEST_CONN_ID}", json=body)
        assert response.status_code == 200

    @pytest.mark.parametrize(
        "body, updated_connection, update_mask",
        [
            (
                {"connection_id": TEST_CONN_ID, "conn_type": TEST_CONN_TYPE, "extra": '{"key": "var"}'},
                {
                    "connection_id": TEST_CONN_ID,
                    "conn_type": TEST_CONN_TYPE,
                    "extra": None,
                    "host": TEST_CONN_HOST,
                    "login": TEST_CONN_LOGIN,
                    "port": TEST_CONN_PORT,
                    "schema": None,
                    "password": None,
                    "description": TEST_CONN_DESCRIPTION,
                },
                {"update_mask": ["login", "port"]},
            ),
            (
                {"connection_id": TEST_CONN_ID, "conn_type": TEST_CONN_TYPE, "host": "test_host_patch"},
                {
                    "connection_id": TEST_CONN_ID,
                    "conn_type": TEST_CONN_TYPE,
                    "extra": None,
                    "host": "test_host_patch",
                    "login": TEST_CONN_LOGIN,
                    "port": TEST_CONN_PORT,
                    "schema": None,
                    "password": None,
                    "description": TEST_CONN_DESCRIPTION,
                },
                {"update_mask": ["host"]},
            ),
            (
                {
                    "connection_id": TEST_CONN_ID,
                    "conn_type": TEST_CONN_TYPE,
                    "host": "test_host_patch",
                    "port": 80,
                },
                {
                    "connection_id": TEST_CONN_ID,
                    "conn_type": TEST_CONN_TYPE,
                    "extra": None,
                    "host": "test_host_patch",
                    "login": TEST_CONN_LOGIN,
                    "port": 80,
                    "schema": None,
                    "password": None,
                    "description": TEST_CONN_DESCRIPTION,
                },
                {"update_mask": ["host", "port"]},
            ),
            (
                {"connection_id": TEST_CONN_ID, "conn_type": TEST_CONN_TYPE, "login": "test_login_patch"},
                {
                    "connection_id": TEST_CONN_ID,
                    "conn_type": TEST_CONN_TYPE,
                    "extra": None,
                    "host": TEST_CONN_HOST,
                    "login": "test_login_patch",
                    "port": TEST_CONN_PORT,
                    "schema": None,
                    "password": None,
                    "description": TEST_CONN_DESCRIPTION,
                },
                {"update_mask": ["login"]},
            ),
            (
                {
                    "connection_id": TEST_CONN_ID,
                    "conn_type": TEST_CONN_TYPE,
                    "host": TEST_CONN_HOST,
                    "port": 80,
                },
                {
                    "connection_id": TEST_CONN_ID,
                    "conn_type": TEST_CONN_TYPE,
                    "extra": None,
                    "host": TEST_CONN_HOST,
                    "login": TEST_CONN_LOGIN,
                    "port": TEST_CONN_PORT,
                    "password": None,
                    "schema": None,
                    "description": TEST_CONN_DESCRIPTION,
                },
                {"update_mask": ["host"]},
            ),
        ],
    )
    def test_patch_should_respond_200_with_update_mask(
        self, test_client, session, body, updated_connection, update_mask
    ):
        self.create_connection()
        response = test_client.patch(f"/public/connections/{TEST_CONN_ID}", json=body, params=update_mask)
        assert response.status_code == 200
        connection = session.query(Connection).filter_by(conn_id=TEST_CONN_ID).first()
        assert connection.password is None
        assert response.json() == updated_connection

    @pytest.mark.parametrize(
        "body",
        [
            {
                "connection_id": "i_am_not_a_connection",
                "conn_type": TEST_CONN_TYPE,
                "extra": '{"key": "var"}',
            },
            {
                "connection_id": "i_am_not_a_connection",
                "conn_type": TEST_CONN_TYPE,
                "host": "test_host_patch",
            },
            {
                "connection_id": "i_am_not_a_connection",
                "conn_type": TEST_CONN_TYPE,
                "host": "test_host_patch",
                "port": 80,
            },
            {
                "connection_id": "i_am_not_a_connection",
                "conn_type": TEST_CONN_TYPE,
                "login": "test_login_patch",
            },
            {"connection_id": "i_am_not_a_connection", "conn_type": TEST_CONN_TYPE, "port": 80},
            {
                "connection_id": "i_am_not_a_connection",
                "conn_type": TEST_CONN_TYPE,
                "port": 80,
                "login": "test_login_patch",
            },
        ],
    )
    def test_patch_should_respond_400(self, test_client, body):
        self.create_connection()
        response = test_client.patch(f"/public/connections/{TEST_CONN_ID}", json=body)
        assert response.status_code == 400
        assert response.json() == {
            "detail": "The connection_id in the request body does not match the URL parameter",
        }

    @pytest.mark.parametrize(
        "body",
        [
            {
                "connection_id": "i_am_not_a_connection",
                "conn_type": TEST_CONN_TYPE,
                "extra": '{"key": "var"}',
            },
            {
                "connection_id": "i_am_not_a_connection",
                "conn_type": TEST_CONN_TYPE,
                "host": "test_host_patch",
            },
            {
                "connection_id": "i_am_not_a_connection",
                "conn_type": TEST_CONN_TYPE,
                "host": "test_host_patch",
                "port": 80,
            },
            {
                "connection_id": "i_am_not_a_connection",
                "conn_type": TEST_CONN_TYPE,
                "login": "test_login_patch",
            },
            {"connection_id": "i_am_not_a_connection", "conn_type": TEST_CONN_TYPE, "port": 80},
            {
                "connection_id": "i_am_not_a_connection",
                "conn_type": TEST_CONN_TYPE,
                "port": 80,
                "login": "test_login_patch",
            },
        ],
    )
    def test_patch_should_respond_404(self, test_client, body):
        response = test_client.patch(f"/public/connections/{body['connection_id']}", json=body)
        assert response.status_code == 404
        assert response.json() == {
            "detail": f"The Connection with connection_id: `{body['connection_id']}` was not found",
        }

    @pytest.mark.enable_redact
    @pytest.mark.parametrize(
        "body, expected_response",
        [
            (
                {"connection_id": TEST_CONN_ID, "conn_type": TEST_CONN_TYPE, "password": "test-password"},
                {
                    "connection_id": TEST_CONN_ID,
                    "conn_type": TEST_CONN_TYPE,
                    "description": None,
                    "extra": None,
                    "host": None,
                    "login": None,
                    "password": "***",
                    "port": None,
                    "schema": None,
                },
            ),
            (
                {"connection_id": TEST_CONN_ID, "conn_type": TEST_CONN_TYPE, "password": "?>@#+!_%()#"},
                {
                    "connection_id": TEST_CONN_ID,
                    "conn_type": TEST_CONN_TYPE,
                    "description": None,
                    "extra": None,
                    "host": None,
                    "login": None,
                    "password": "***",
                    "port": None,
                    "schema": None,
                },
            ),
            (
                {
                    "connection_id": TEST_CONN_ID,
                    "conn_type": TEST_CONN_TYPE,
                    "password": "A!rF|0wi$aw3s0m3",
                    "extra": '{"password": "test-password"}',
                },
                {
                    "connection_id": TEST_CONN_ID,
                    "conn_type": TEST_CONN_TYPE,
                    "description": None,
                    "extra": '{"password": "***"}',
                    "host": None,
                    "login": None,
                    "password": "***",
                    "port": None,
                    "schema": None,
                },
            ),
        ],
    )
    def test_patch_should_response_200_redacted_password(self, test_client, session, body, expected_response):
        self.create_connections()
        response = test_client.patch(f"/public/connections/{TEST_CONN_ID}", json=body)
        assert response.status_code == 200
        assert response.json() == expected_response


class TestConnection(TestConnectionEndpoint):
    @mock.patch.dict(os.environ, {"AIRFLOW__CORE__TEST_CONNECTION": "Enabled"})
    @pytest.mark.parametrize(
        "body",
        [
            {"connection_id": TEST_CONN_ID, "conn_type": "sqlite"},
            {"connection_id": TEST_CONN_ID, "conn_type": "ftp"},
        ],
    )
    def test_should_respond_200(self, test_client, body):
        response = test_client.post("/public/connections/test", json=body)
        assert response.status_code == 200
        assert response.json() == {
            "status": True,
            "message": "Connection successfully tested",
        }

    @mock.patch.dict(os.environ, {"AIRFLOW__CORE__TEST_CONNECTION": "Enabled"})
    @pytest.mark.parametrize(
        "body",
        [
            {"connection_id": TEST_CONN_ID, "conn_type": "sqlite"},
            {"connection_id": TEST_CONN_ID, "conn_type": "ftp"},
        ],
    )
    def test_connection_env_is_cleaned_after_run(self, test_client, body):
        test_client.post("/public/connections/test", json=body)
        assert not any([key.startswith(CONN_ENV_PREFIX) for key in os.environ.keys()])

    @pytest.mark.parametrize(
        "body",
        [
            {"connection_id": TEST_CONN_ID, "conn_type": "sqlite"},
            {"connection_id": TEST_CONN_ID, "conn_type": "ftp"},
        ],
    )
    def test_should_respond_403_by_default(self, test_client, body):
        response = test_client.post("/public/connections/test", json=body)
        assert response.status_code == 403
        assert response.json() == {
            "detail": "Testing connections is disabled in Airflow configuration. "
            "Contact your deployment admin to enable it."
        }


class TestCreateDefaultConnections(TestConnectionEndpoint):
    def test_should_respond_204(self, test_client):
        response = test_client.post("/public/connections/defaults")
        assert response.status_code == 204
        assert response.content == b""

    @mock.patch("airflow.api_fastapi.core_api.routes.public.connections.db_create_default_connections")
    def test_should_call_db_create_default_connections(self, mock_db_create_default_connections, test_client):
        response = test_client.post("/public/connections/defaults")
        assert response.status_code == 204
        mock_db_create_default_connections.assert_called_once()
