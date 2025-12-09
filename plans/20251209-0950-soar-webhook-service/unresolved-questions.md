# Unresolved Questions

## Configuration

1. **YAML file location** - Which cluster should webhook target?
   - Production cluster?
   - Dedicated security cluster?
   - Multiple clusters (need routing logic)?

2. **Object path structure** - Exact YAML structure?
   - Confirmed: `ip_lists.global.blocklist`?
   - Or different structure per cluster?
   - Example YAML needed for validation

3. **GitLab project** - Same repo as firewall-gitops?
   - Or separate security-blocks repo?
   - Branch strategy: Always main? Or environment-specific?

## Behavior

4. **Duplicate IP handling** - Should webhook return success if IP exists?
   - Current plan: Yes (idempotent, no MR created)
   - Or return 409 Conflict?

5. **MR auto-merge** - Should service auto-merge MRs?
   - Current plan: Manual review required
   - Or auto-merge after CI passes?

6. **IP format** - Always add /32 CIDR?
   - Current plan: Yes (normalize to /32)
   - Or preserve original format?

7. **Attacker types** - Support only ip_v4?
   - Current plan: Reject others (400 error)
   - Future: ip_v6, domain, url?

## Operations

8. **Rate limiting** - How many requests per minute?
   - Unlimited (trust SOAR)?
   - Or implement per-IP rate limit?

9. **Monitoring** - What metrics needed?
   - Prometheus metrics?
   - Just structured logs?

10. **Alerting** - Notify on webhook failures?
    - Slack integration?
    - Email alerts?
    - Or rely on monitoring system?

## Deployment

11. **Where to deploy** - Hosting location?
    - Same infrastructure as GitLab runners?
    - Separate VM/container?
    - Cloud function (serverless)?

12. **High availability** - Single instance sufficient?
    - Or need multiple replicas?
    - Load balancer required?

13. **Secrets management** - How to store GITLAB_TOKEN?
    - Environment variables in deployment?
    - GitLab CI/CD variables?
    - External secrets manager (Vault)?

## Testing

14. **Test environment** - Need separate GitLab project for tests?
    - Use production project with test branch?
    - Or dedicated test project?

15. **Test data cleanup** - Who removes test IPs from blocklist?
    - Manual cleanup?
    - Automated test teardown?
