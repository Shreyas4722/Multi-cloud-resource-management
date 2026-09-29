"""Provider adapter tests. All boto3 calls are mocked -- no test here needs
real cloud credentials."""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

from cloudlens.config import AWSProviderConfig, ColumnMapping, CSVProviderConfig
from cloudlens.models import ResourceState, ResourceType
from cloudlens.providers.aws import AWSAdapter
from cloudlens.providers.azure import AzureAdapter
from cloudlens.providers.gcp import GCPAdapter


def _paginator(pages):
    p = MagicMock()
    p.paginate.return_value = pages
    return p


def test_aws_fetch_resources_maps_instances_and_volumes():
    ec2 = MagicMock()

    def get_paginator(op_name):
        if op_name == "describe_instances":
            return _paginator(
                [
                    {
                        "Reservations": [
                            {
                                "OwnerId": "123456789012",
                                "Instances": [
                                    {
                                        "InstanceId": "i-abc",
                                        "InstanceType": "t3.medium",
                                        "State": {"Name": "running"},
                                        "Tags": [{"Key": "project", "Value": "web-app"}],
                                        "LaunchTime": datetime.now(timezone.utc),
                                    }
                                ],
                            }
                        ]
                    }
                ]
            )
        return _paginator(
            [
                {
                    "Volumes": [
                        {
                            "VolumeId": "vol-xyz",
                            "VolumeType": "gp3",
                            "Size": 100,
                            "State": "available",
                            "Tags": [],
                            "Attachments": [],
                        }
                    ]
                }
            ]
        )

    ec2.get_paginator.side_effect = get_paginator

    with patch("boto3.client", return_value=ec2):
        adapter = AWSAdapter(AWSProviderConfig(enabled=True, regions=["us-east-1"]))
        resources = adapter.fetch_resources()

    by_id = {r.id: r for r in resources}
    assert by_id["i-abc"].resource_type == ResourceType.COMPUTE
    assert by_id["i-abc"].state == ResourceState.RUNNING
    assert by_id["vol-xyz"].resource_type == ResourceType.STORAGE
    assert by_id["vol-xyz"].state == ResourceState.UNATTACHED


def test_aws_fetch_utilization_from_cloudwatch():
    cloudwatch = MagicMock()
    cloudwatch.get_metric_statistics.return_value = {
        "Datapoints": [{"Average": 3.0, "Maximum": 8.0}, {"Average": 5.0, "Maximum": 12.0}]
    }
    with patch("boto3.client", return_value=cloudwatch):
        adapter = AWSAdapter(AWSProviderConfig(enabled=True, regions=["us-east-1"]))
        stats = adapter.fetch_utilization("i-abc", 7)

    assert stats.avg_cpu == 4.0
    assert stats.max_cpu == 12.0


def test_aws_fetch_utilization_returns_none_without_datapoints():
    cloudwatch = MagicMock()
    cloudwatch.get_metric_statistics.return_value = {"Datapoints": []}
    with patch("boto3.client", return_value=cloudwatch):
        adapter = AWSAdapter(AWSProviderConfig(enabled=True, regions=["us-east-1"]))
        assert adapter.fetch_utilization("i-abc", 7) is None


def test_aws_fetch_costs_from_cur_csv(tmp_path):
    csv_path = tmp_path / "cur.csv"
    csv_path.write_text(
        "usage_date,resource_id,service,project,amount,currency\n"
        "2026-09-01,i-abc,EC2,web-app,12.5,USD\n"
        "2026-08-01,i-abc,EC2,web-app,11.0,USD\n"
    )
    adapter = AWSAdapter(AWSProviderConfig(enabled=True, regions=["us-east-1"], cur_csv_path=str(csv_path)))
    costs = adapter.fetch_costs(date(2026, 9, 1), date(2026, 9, 30))
    assert len(costs) == 1
    assert costs[0].amount == 12.5


def test_azure_adapter_reads_csv_with_configured_columns(tmp_path):
    cost_csv = tmp_path / "azure_costs.csv"
    cost_csv.write_text("UsageDate,Cost,ServiceName,ResourceId,ResourceGroup,Currency\n2026-09-01,45.2,Virtual Machines,vm-1,web-app,USD\n")
    inventory_csv = tmp_path / "azure_inventory.csv"
    inventory_csv.write_text(
        "ResourceId,ResourceType,Location,PowerState,Size,Tags,CreatedTime\n"
        'vm-1,Virtual Machines,eastus,VM running,Standard_B2s,"{""project"": ""web-app""}",2026-01-01\n'
        "disk-1,Managed Disks,eastus,unattached,Premium_LRS,project=web-app,2026-01-01\n"
    )
    mapping = ColumnMapping(
        cost={"date": "UsageDate", "amount": "Cost", "service": "ServiceName", "resource_id": "ResourceId", "project": "ResourceGroup", "currency": "Currency"},
        inventory={"id": "ResourceId", "type": "ResourceType", "region": "Location", "state": "PowerState", "size": "Size", "tags": "Tags", "created_at": "CreatedTime"},
    )
    adapter = AzureAdapter(
        CSVProviderConfig(enabled=True, cost_csv_path=str(cost_csv), inventory_csv_path=str(inventory_csv), account_id="sub-1", column_mapping=mapping)
    )

    resources = {r.id: r for r in adapter.fetch_resources()}
    assert resources["vm-1"].resource_type == ResourceType.COMPUTE
    assert resources["vm-1"].state == ResourceState.RUNNING
    assert resources["disk-1"].state == ResourceState.UNATTACHED
    assert resources["disk-1"].attached is False

    costs = adapter.fetch_costs(date(2026, 9, 1), date(2026, 9, 30))
    assert len(costs) == 1
    assert costs[0].project == "web-app"
    assert adapter.fetch_utilization("vm-1", 7) is None


def test_gcp_adapter_reads_csv_with_configured_columns(tmp_path):
    cost_csv = tmp_path / "gcp_costs.csv"
    cost_csv.write_text("usage_start_date,cost,service_description,resource_name,project_id,currency\n2026-09-01,30.0,Compute Engine,instance-1,data-platform,USD\n")
    inventory_csv = tmp_path / "gcp_inventory.csv"
    inventory_csv.write_text(
        "resource_name,resource_type,zone,status,machine_type,labels,creation_timestamp\n"
        "instance-1,Compute Engine,us-central1,running,e2-medium,project=data-platform,2026-01-01\n"
    )
    mapping = ColumnMapping(
        cost={"date": "usage_start_date", "amount": "cost", "service": "service_description", "resource_id": "resource_name", "project": "project_id", "currency": "currency"},
        inventory={"id": "resource_name", "type": "resource_type", "region": "zone", "state": "status", "size": "machine_type", "tags": "labels", "created_at": "creation_timestamp"},
    )
    adapter = GCPAdapter(
        CSVProviderConfig(enabled=True, cost_csv_path=str(cost_csv), inventory_csv_path=str(inventory_csv), account_id="proj-1", column_mapping=mapping)
    )

    resources = adapter.fetch_resources()
    assert len(resources) == 1
    assert resources[0].resource_type == ResourceType.COMPUTE
    assert resources[0].hourly_cost > 0  # matched e2-medium in pricing.json

    costs = adapter.fetch_costs(date(2026, 9, 1), date(2026, 9, 30))
    assert costs[0].amount == 30.0
