"""AWS provider adapter.

Uses boto3 in strictly read-only mode: `describe_instances`, `describe_volumes`,
`get_metric_statistics` and `get_cost_and_usage` only. Never creates, modifies
or deletes any AWS resource. Credentials are never hardcoded -- boto3 picks
them up from environment variables or the standard AWS credentials chain
(shared config file, instance profile, SSO, etc.).

Cost data defaults to reading a local AWS Cost and Usage Report (CUR) export,
because Cost Explorer API calls are billed per request. The CUR CSV is
expected in this simplified, flattened shape (one row per resource per day):

    usage_date, resource_id, service, project, amount, currency

Set `cost_source: cost_explorer` in config to call the Cost Explorer API
instead.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pandas as pd

from cloudlens.config import AWSProviderConfig
from cloudlens.models import CostRecord, Resource, UtilizationStats
from cloudlens.normalizer import normalize_resource_type, normalize_state
from cloudlens.pricing import load_pricing
from cloudlens.providers.base import ProviderAdapter
from cloudlens.registry import register_provider

CUR_CSV_COLUMNS = ["usage_date", "resource_id", "service", "project", "amount", "currency"]


@register_provider("aws")
class AWSAdapter(ProviderAdapter):
    """Read-only adapter for a real AWS account (EC2, EBS, CloudWatch, costs)."""

    def __init__(self, config: AWSProviderConfig):
        self.config = config
        self._pricing = load_pricing()["aws"]

    def name(self) -> str:
        return "aws"

    def _client(self, service: str, region: str | None = None):
        import boto3

        return boto3.client(service, region_name=region) if region else boto3.client(service)

    # -- resources ------------------------------------------------------

    def fetch_resources(self) -> list[Resource]:
        resources: list[Resource] = []
        for region in self.config.regions:
            resources.extend(self._fetch_instances(region))
            resources.extend(self._fetch_volumes(region))
        return resources

    def _fetch_instances(self, region: str) -> list[Resource]:
        ec2 = self._client("ec2", region)
        resources: list[Resource] = []
        paginator = ec2.get_paginator("describe_instances")
        for page in paginator.paginate():
            for reservation in page.get("Reservations", []):
                account_id = reservation.get("OwnerId", self.config.account_id)
                for instance in reservation.get("Instances", []):
                    instance_type = instance.get("InstanceType", "")
                    tags = {t["Key"]: t["Value"] for t in instance.get("Tags", [])}
                    hourly = self._pricing.get("compute", {}).get(instance_type, {}).get("hourly", 0.0)
                    resources.append(
                        Resource(
                            id=instance["InstanceId"],
                            provider="aws",
                            account_id=account_id,
                            region=region,
                            resource_type=normalize_resource_type("aws", "ec2"),
                            instance_size=instance_type,
                            state=normalize_state("aws", instance.get("State", {}).get("Name", "")),
                            tags=tags,
                            created_at=instance.get("LaunchTime", datetime.now(timezone.utc)),
                            hourly_cost=hourly,
                            project=tags.get("project"),
                        )
                    )
        return resources

    def _fetch_volumes(self, region: str) -> list[Resource]:
        ec2 = self._client("ec2", region)
        resources: list[Resource] = []
        paginator = ec2.get_paginator("describe_volumes")
        for page in paginator.paginate():
            for volume in page.get("Volumes", []):
                volume_type = volume.get("VolumeType", "gp3")
                size_gb = volume.get("Size", 0)
                price_per_gb = self._pricing.get("storage", {}).get(volume_type, {}).get("hourly_per_gb", 0.0)
                tags = {t["Key"]: t["Value"] for t in volume.get("Tags", [])}
                attachments = volume.get("Attachments", [])
                resources.append(
                    Resource(
                        id=volume["VolumeId"],
                        provider="aws",
                        account_id=self.config.account_id,
                        region=region,
                        resource_type=normalize_resource_type("aws", "ebs"),
                        instance_size=f"{size_gb}GB {volume_type}",
                        state=normalize_state("aws", volume.get("State", "")),
                        tags=tags,
                        created_at=volume.get("CreateTime", datetime.now(timezone.utc)),
                        hourly_cost=price_per_gb * size_gb,
                        project=tags.get("project"),
                        attached=bool(attachments),
                        attached_to=attachments[0]["InstanceId"] if attachments else None,
                    )
                )
        return resources

    # -- costs ------------------------------------------------------------

    def fetch_costs(self, start_date: date, end_date: date) -> list[CostRecord]:
        if self.config.cost_source == "cost_explorer":
            return self._fetch_costs_from_cost_explorer(start_date, end_date)
        return self._fetch_costs_from_cur_csv(start_date, end_date)

    def _fetch_costs_from_cur_csv(self, start_date: date, end_date: date) -> list[CostRecord]:
        if not self.config.cur_csv_path:
            return []
        df = pd.read_csv(self.config.cur_csv_path)
        missing = set(CUR_CSV_COLUMNS) - set(df.columns)
        if missing:
            raise ValueError(f"AWS CUR CSV is missing expected columns: {sorted(missing)}")

        df["usage_date"] = pd.to_datetime(df["usage_date"]).dt.date
        df = df[(df["usage_date"] >= start_date) & (df["usage_date"] <= end_date)]

        return [
            CostRecord(
                provider="aws",
                account_id=self.config.account_id,
                resource_id=row.get("resource_id") or None,
                service=row["service"],
                project=row.get("project") or None,
                date=row["usage_date"],
                amount=float(row["amount"]),
                currency=row.get("currency", "USD"),
            )
            for _, row in df.iterrows()
        ]

    def _fetch_costs_from_cost_explorer(self, start_date: date, end_date: date) -> list[CostRecord]:
        ce = self._client("ce")
        records: list[CostRecord] = []
        response = ce.get_cost_and_usage(
            TimePeriod={"Start": start_date.isoformat(), "End": (end_date + timedelta(days=1)).isoformat()},
            Granularity="DAILY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )
        for result in response.get("ResultsByTime", []):
            day = date.fromisoformat(result["TimePeriod"]["Start"])
            for group in result.get("Groups", []):
                service = group["Keys"][0]
                amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
                currency = group["Metrics"]["UnblendedCost"]["Unit"]
                records.append(
                    CostRecord(
                        provider="aws",
                        account_id=self.config.account_id,
                        resource_id=None,
                        service=service,
                        project=None,
                        date=day,
                        amount=amount,
                        currency=currency,
                    )
                )
        return records

    # -- utilization --------------------------------------------------------

    def fetch_utilization(self, resource_id: str, days: int) -> UtilizationStats | None:
        cloudwatch = self._client("cloudwatch")
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=days)
        response = cloudwatch.get_metric_statistics(
            Namespace="AWS/EC2",
            MetricName="CPUUtilization",
            Dimensions=[{"Name": "InstanceId", "Value": resource_id}],
            StartTime=start_time,
            EndTime=end_time,
            Period=3600,
            Statistics=["Average", "Maximum"],
        )
        datapoints = response.get("Datapoints", [])
        if not datapoints:
            return None

        avg_cpu = sum(dp["Average"] for dp in datapoints) / len(datapoints)
        max_cpu = max(dp["Maximum"] for dp in datapoints)
        return UtilizationStats(resource_id=resource_id, avg_cpu=avg_cpu, max_cpu=max_cpu, period_days=days)
