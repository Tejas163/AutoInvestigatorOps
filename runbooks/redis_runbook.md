# Runbook: Redis Connection Pooling Outages
**Target Service:** payment-gateway-v2, core-api
**Symptoms:** Connection Timeout, MAX_EXHAUSTED client states.

### Root Cause Analysis
This usually happens when application traffic spikes, or when connection lifecycles are not terminated properly, causing untracked idle connections to hog the Redis instance limits.

### Remediation Action
1. Connect to the cluster via terminal.
2. Execute the CLI command: `CLIENT KILL TYPE normal` to safely flush out rogue idle connection slots.
3. Update the application config `REDIS_MAX_CONNECTIONS` parameter to 300 in the staging or production deployment script.