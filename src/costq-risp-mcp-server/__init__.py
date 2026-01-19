# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""CostQ RISP (Reserved Instance & Savings Plans) MCP Server.

This module provides MCP tools for analyzing AWS Reserved Instances and Savings Plans
through the AWS Cost Explorer API.

This is a standalone version without multi-account support, designed for deployment
as an independent MCP server via AgentCore Gateway.
"""

__version__ = "1.0.0"
__author__ = "CostQ Team"
__description__ = "CostQ RISP MCP Server for Reserved Instance and Savings Plans analysis"
