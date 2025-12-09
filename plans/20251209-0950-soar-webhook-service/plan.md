# SOAR Webhook Service Implementation Plan

**Created:** 2025-12-09
**Status:** In Progress
**Location:** `scripts/webhook-soar/`

## Overview

Lightweight Go webhook service receiving SOAR alerts, extracting attacker IPs, updating YAML blocklists in GitLab repo via merge requests.

## Phases

| Phase | Description | Status |
|-------|-------------|--------|
| [01](phase-01-project-setup.md) | Project setup & configuration | **Done** (2025-12-09) |
| [02](phase-02-gitlab-integration.md) | GitLab API integration | Next |
| [03](phase-03-yaml-processor.md) | YAML parsing & IP management | Pending |
| [04](phase-04-webhook-handler.md) | HTTP webhook handler | Pending |
| [05](phase-05-testing-deployment.md) | Testing & deployment | Pending |

## Key Dependencies

- Go 1.21+ runtime
- GitLab API v4 access
- Environment variables for config

## Architecture Summary

```
SOAR Alert → HTTP POST → Webhook Handler → Git Pull → YAML Update → Git Commit → Create MR
```

**Components:**
1. HTTP server (net/http)
2. GitLab API client (go-gitlab SDK)
3. YAML parser (gopkg.in/yaml.v3)
4. Config loader (environment vars)

## Configuration

Via `variables.tf` (Terraform variables pattern):
- `gitlab_url` - GitLab instance URL
- `gitlab_token` - Personal access token
- `gitlab_project_id` - Project ID
- `gitlab_branch` - Target branch (default: main)
- `yaml_file_path` - Path to YAML file in repo
- `object_path` - YAML object path (default: ip_lists.global.blocklist)

## Success Criteria

- Receives SOAR webhook POST
- Parses attacker IP from body
- Updates YAML without duplicates
- Creates MR (not direct push)
- Handles concurrent requests
- Logs all operations
