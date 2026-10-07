# CloudLens

A multi-cloud resource management and cost optimization **framework** for AWS, Azure and Google Cloud.

## The problem

Organizations running workloads across several clouds have no single view of what they own and what it
costs. Every provider has its own console, billing format and pricing model, so idle instances,
unattached disks and oversized machines go unnoticed while money leaks away. CloudLens collects
resource and cost data from every provider, converts it into one common format, detects waste, estimates
the savings from fixing it, tracks budgets, and shows all of it in one dashboard.

CloudLens is a **framework**, not a single script:

- New cloud providers are added by writing a **provider adapter** that implements a standard interface —
  no changes to core code.
- New optimization checks are added by writing a **rule plugin** that registers itself with the rules
  engine — no changes to core code.
- The CLI and the Streamlit dashboard are thin **consumers** of the framework's public API. Neither
  contains any business logic of its own.

It runs entirely offline in **demo mode** (generated sample data, no cloud credentials needed), and can
also connect to a real AWS account in **strictly read-only** mode. CloudLens never creates, modifies or
deletes any cloud resource — it only reads and recommends.

## Architecture

```
Browser  ──►  Streamlit dashboard (dashboard/)
                    │  calls the public API only
                    ▼
             cloudlens package
                    │
   ┌────────────────┼──────────────────────────────────────────┐
   ▼                ▼                    ▼                     ▼
Provider         Normalizer          Storage              Rules Engine
Adapters   ──►   (common schema) ──► (SQLite via      ──► + Budget Engine
(AWS, Azure,                          SQLAlchemy)          (recommendations,
 GCP, Demo)                                                 savings, alerts)
                                                                   │
                                                                   ▼
                                                          CLI (cloudlens ...)
                                                          & Dashboard, both
                                                          via CloudLens API
```

- **Provider Adapters** (`cloudlens/providers/`) fetch resources, costs and utilization from a cloud
  account or from exported CSVs, and return them already normalized to the common models.
- **Normalizer** (`cloudlens/normalizer.py`) holds the single, editable table mapping each provider's
  native resource-type/state strings ("EC2", "Virtual Machines", "Compute Engine", ...) to a common
  vocabulary.
- **Storage** (`cloudlens/storage/`) is a SQLAlchemy + SQLite layer with a repository module; re-running a
  sync updates existing rows instead of creating duplicates.
- **Rules Engine** (`cloudlens/rules/`) runs every registered, enabled rule against every resource and
  produces `Recommendation`s.
- **Budget Engine** (`cloudlens/budget/`) computes month-to-date spend per project, raises alerts at
  configurable thresholds, and forecasts end-of-month spend.
- **`CloudLens`** (`cloudlens/core.py`) is the single public entry point everything else calls.

## Installation and quick start (demo mode)

Requires Python 3.11+.

```bash
git clone <this-repo>
cd cloudlens
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cloudlens demo        # generates sample data, syncs, analyzes, prints a report
```

Then open the dashboard:

```bash
streamlit run dashboard/app.py
# → http://localhost:8501
```

Demo mode is on by default (`demo_mode: true` in `config.example.yaml`) and needs no cloud credentials at
all — it generates 70+ realistic AWS/Azure/GCP resources with a deliberate mix of healthy and wasteful
ones, so every rule has something to find.

### CLI reference

```bash
cloudlens init      # create config.yaml from config.example.yaml
cloudlens sync       # fetch and store resources + costs from all enabled providers
cloudlens analyze    # run all rules and budget checks
cloudlens report     # print a summary of costs, top recommendations and budget status
cloudlens export --format csv -o recommendations.csv
cloudlens demo       # init (if needed) + sync + analyze + report, on sample data
```

The CLI and the dashboard share the same `config.yaml` and SQLite database, so a sync run from a
terminal shows up in the dashboard on next refresh.

## Running with Docker

```bash
docker-compose up --build
# → http://localhost:8501
```

On first run, the container creates `data/config.yaml` from `config.example.yaml` (demo mode), runs an
initial sync + analyze, then serves the dashboard. `./data` is bind-mounted so `config.yaml` and
`cloudlens.db` persist across restarts — edit `data/config.yaml` on the host to point at real providers,
then `docker-compose restart`.

## Deploying

- **Streamlit Community Cloud**: point it at this repo, entry point `dashboard/app.py`. Leave
  `demo_mode: true` in the config that ships with the deployment — there's no way to hand it real AWS
  credentials safely on a public shared host.
- **AWS EC2 (free tier)**: launch a small instance, install Docker, `git clone` this repo, open port
  `8501` in the instance's security group (source: your IP, not `0.0.0.0/0`, unless you intend public
  access), then `docker-compose up -d`. To read a real account, export the AWS credentials below into the
  shell before `docker-compose up`, or attach an IAM instance role with the same policy instead of static
  keys.

## Connecting a real AWS account (read-only)

CloudLens never hardcodes credentials — it reads them from environment variables or the standard AWS
credentials chain (`~/.aws/credentials`, instance profile, SSO, etc.). Set:

```bash
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=us-east-1
```

Then in `config.yaml`:

```yaml
demo_mode: false
providers:
  aws:
    enabled: true
    regions: ["us-east-1", "us-west-2"]
    cost_source: csv          # or cost_explorer -- see note below
    cur_csv_path: "sample_data/aws_cur.csv"
```

Attach this least-privilege, read-only IAM policy to the user or role CloudLens runs as:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CloudLensReadOnlyEC2",
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeInstances",
        "ec2:DescribeVolumes",
        "ec2:DescribeRegions"
      ],
      "Resource": "*"
    },
    {
      "Sid": "CloudLensReadOnlyCloudWatch",
      "Effect": "Allow",
      "Action": [
        "cloudwatch:GetMetricStatistics",
        "cloudwatch:ListMetrics"
      ],
      "Resource": "*"
    },
    {
      "Sid": "CloudLensReadOnlyCostExplorer",
      "Effect": "Allow",
      "Action": [
        "ce:GetCostAndUsage"
      ],
      "Resource": "*"
    }
  ]
}
```

The `ce:GetCostAndUsage` statement is only needed if you set `cost_source: cost_explorer`. The default,
`cost_source: csv`, reads a local AWS Cost and Usage Report (CUR) export instead, since Cost Explorer API
calls are billed per request. Generate one from **Billing and Cost Management → Cost & Usage Reports** in
the AWS Console, or point `cur_csv_path` at a simplified extract with these columns:

```
usage_date, resource_id, service, project, amount, currency
```

## Exporting Azure and GCP billing CSVs

CloudLens's Azure and GCP adapters are entirely CSV-driven (no API calls, no credentials) — export two
files per provider and point `config.yaml` at them.

**Azure:**
1. Cost export: Azure Portal → **Cost Management + Billing → Cost Management → Exports** → create a
   one-time or scheduled export, download the CSV.
2. Resource inventory: Azure Portal → **Resource Graph Explorer**, or `az resource list -o json`
   converted to CSV, or **Azure Resource Inventory** exports.

**Google Cloud:**
1. Cost export: enable **BigQuery Billing Export** (Billing → Billing export), then run a query and export
   the results to CSV, or use **Reports → Download CSV** in the Billing console for a quick one-off.
2. Resource inventory: `gcloud asset export` or Cloud Asset Inventory's CSV export, or
   `gcloud compute instances list --format=csv(...)` / `gcloud compute disks list --format=csv(...)`.

Column names vary by export format and change over time, so `config.yaml` maps them explicitly:

```yaml
providers:
  azure:
    enabled: true
    cost_csv_path: "sample_data/azure_costs.csv"
    inventory_csv_path: "sample_data/azure_inventory.csv"
    column_mapping:
      cost:
        date: "UsageDate"
        amount: "Cost"
        service: "ServiceName"
        resource_id: "ResourceId"
        project: "ResourceGroup"
        currency: "Currency"
      inventory:
        id: "ResourceId"
        type: "ResourceType"
        region: "Location"
        state: "PowerState"
        size: "Size"
        tags: "Tags"
        created_at: "CreatedTime"
```

Sample CSVs matching this exact mapping are in `sample_data/` for both providers.

**Known limitation:** unlike AWS (which prices resources from the bundled `pricing.json` by instance
type) and unlike costs (which always come from the accurate billing export), a CSV-sourced *storage*
resource's `hourly_cost` field defaults to `$0` because a generic inventory export has no reliable
GB-size column to price against. This means the `unattached_storage` rule still fires correctly for
Azure/GCP storage, but its estimated saving may show as $0 until you extend `_csv_common.py` to parse a
size column specific to your export format.

## Extending the framework

Both extension points are additive: drop in a file, and it's picked up automatically. Neither
`cloudlens/core.py` nor `cloudlens/rules/engine.py` needs to change.

### Adding a new provider adapter

Create `cloudlens/providers/oracle.py`:

```python
from cloudlens.providers.base import ProviderAdapter
from cloudlens.registry import register_provider

@register_provider("oracle")
class OracleAdapter(ProviderAdapter):
    def __init__(self, config):
        self.config = config

    def name(self) -> str:
        return "oracle"

    def fetch_resources(self):
        ...  # return list[Resource]

    def fetch_costs(self, start_date, end_date):
        ...  # return list[CostRecord]

    def fetch_utilization(self, resource_id, days):
        ...  # return UtilizationStats | None
```

Add an `oracle:` section under `providers:` in `config.yaml` with `enabled: true`, and `CloudLens.sync()`
picks it up on the next run — `cloudlens/core.py` discovers adapters purely through the provider registry
(`pkgutil`-based module discovery + the `@register_provider` decorator), never through a hardcoded
import.

### Adding a new rule

Create `cloudlens/rules/large_database_idle.py`:

```python
from datetime import datetime, timezone
from cloudlens.models import Recommendation, ResourceType, Severity
from cloudlens.registry import register_rule
from cloudlens.rules.base import OptimizationRule

@register_rule
class LargeDatabaseIdleRule(OptimizationRule):
    rule_id = "large_database_idle"
    description = "Flags large database instances with no recent connections."

    def evaluate(self, resource, utilization, context):
        if resource.resource_type != ResourceType.DATABASE:
            return None
        # ... your condition here ...
        return Recommendation(
            id=f"{self.rule_id}:{resource.id}",
            resource_id=resource.id,
            provider=resource.provider,
            rule_id=self.rule_id,
            severity=Severity.MEDIUM,
            title="Idle large database",
            description="...",
            current_monthly_cost=resource.monthly_cost,
            estimated_monthly_saving=resource.monthly_cost,
            suggested_action="Downsize or decommission.",
            created_at=datetime.now(timezone.utc),
        )
```

That's it. `cloudlens analyze` discovers it via `pkgutil` module scanning + the `@register_rule`
decorator, it appears in `cl.get_recommendations()`, and the Recommendations page shows it — with zero
edits to any existing file. Add matching thresholds under `rules.large_database_idle.params` in
`config.yaml` if the rule needs them.

## Testing

```bash
pytest
```

39 tests cover every rule (one triggering case, one non-triggering case), the normalizer's mapping for
each provider, the budget engine's threshold and forecast math, registry discovery (including that a new
adapter/rule registers correctly), the AWS/Azure/GCP adapters (all boto3 calls mocked, Azure/GCP driven
by temp CSVs), and one end-to-end demo `sync()` + `analyze()` run. No test requires real cloud
credentials.

## Project layout

```
cloudlens/
├── cloudlens/            the framework package
│   ├── core.py           CloudLens: the public API
│   ├── models.py         Pydantic models shared by every layer
│   ├── config.py         config.yaml schema + loader
│   ├── normalizer.py     provider-native -> common type/state mapping table
│   ├── registry.py       provider + rule registries
│   ├── providers/        AWSAdapter, AzureAdapter, GCPAdapter, DemoAdapter
│   ├── rules/            the 5 optimization rules + the rules engine
│   ├── budget/           budget engine + notifiers (console, webhook)
│   ├── storage/          SQLAlchemy models + repository
│   ├── data/pricing.json approximate reference cloud pricing
│   └── cli.py            Typer CLI
├── dashboard/            Streamlit app: 6 pages, no business logic
├── sample_data/          example AWS CUR / Azure / GCP CSVs
├── tests/
├── config.example.yaml
├── Dockerfile / docker-compose.yml
└── pyproject.toml
```
# Multi-cloud-resource-management
