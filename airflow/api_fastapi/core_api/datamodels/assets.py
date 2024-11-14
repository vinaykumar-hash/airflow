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

from datetime import datetime

from pydantic import BaseModel, Field


class DagScheduleAssetReference(BaseModel):
    """DAG schedule reference serializer for assets."""

    dag_id: str
    created_at: datetime
    updated_at: datetime


class TaskOutletAssetReference(BaseModel):
    """Task outlet reference serializer for assets."""

    dag_id: str
    task_id: str
    created_at: datetime
    updated_at: datetime


class AssetAliasSchema(BaseModel):
    """Asset alias serializer for assets."""

    id: int
    name: str


class AssetResponse(BaseModel):
    """Asset serializer for responses."""

    id: int
    uri: str
    extra: dict | None = None
    created_at: datetime
    updated_at: datetime
    consuming_dags: list[DagScheduleAssetReference]
    producing_tasks: list[TaskOutletAssetReference]
    aliases: list[AssetAliasSchema]


class AssetCollectionResponse(BaseModel):
    """Asset collection response."""

    assets: list[AssetResponse]
    total_entries: int


class DagRunAssetReference(BaseModel):
    """DAGRun serializer for asset responses."""

    run_id: str
    dag_id: str
    execution_date: datetime = Field(alias="logical_date")
    start_date: datetime
    end_date: datetime
    state: str
    data_interval_start: datetime
    data_interval_end: datetime


class AssetEventResponse(BaseModel):
    """Asset event serializer for responses."""

    id: int
    asset_id: int
    uri: str
    extra: dict | None = None
    source_task_id: str | None = None
    source_dag_id: str | None = None
    source_run_id: str | None = None
    source_map_index: int
    created_dagruns: list[DagRunAssetReference]
    timestamp: datetime


class AssetEventCollectionResponse(BaseModel):
    """Asset event collection response."""

    asset_events: list[AssetEventResponse]
    total_entries: int