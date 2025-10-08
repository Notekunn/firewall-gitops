# Repository Guidelines

## Project Structure & Module Organization
Configurations live in `clusters/<cluster>/` with required `cluster.yaml` (context, positioning, commit policy) and `rules.yaml` (objects and rules). Terraform execution runs from `terraform/`, which loads YAML into `modules/palo-alto`; `modules/shared` is reserved for cross-firewall utilities. Helper tooling (`deploy.sh`, `validate_yaml.py`, `commit.sh`) lives in `scripts/`, schemas in `schemas/`, and Python deps in `requirements.txt`.

## Build, Test, and Development Commands
- `python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`: set up validation dependencies.
- `python scripts/validate_yaml.py`: lint YAML and schema check every cluster.
- `terraform fmt -recursive`: align Terraform formatting before pushing.
- `./scripts/deploy.sh -c <cluster> -a plan [-d]`: create (or dry-run) a GitLab-backed plan for the selected cluster.
- `./scripts/deploy.sh -c <cluster> -a apply -y`: apply a previously created plan once approvals are in place.

## Coding Style & Naming Conventions
- Terraform: two-space indent, `terraform fmt` clean, outputs and variables in `snake_case`.
- YAML: two-space indent, meaningful rule groups (`web_access`, `audit`), object names that mirror firewall expectations, single quotes for strings with special characters.
- Python: follow PEP 8 with four-space indent, pure functions where possible, and guard CLI blocks with `if __name__ == "__main__":`.
- Directory names: lowercase kebab-case (`prod-dmz`); keep cluster file names exactly `cluster.yaml` and `rules.yaml` so automation locates them.

## Testing Guidelines
- Run `python scripts/validate_yaml.py` before every plan; update `schemas/*.json` when adding fields.
- Use `terraform fmt -check` and `terraform validate` (or `./scripts/deploy.sh -c <cluster> -a validate`) to catch drift early.
- Capture the diff from `./scripts/deploy.sh -c <cluster> -a plan` and share key changes in reviews; the script pipes summaries through `jq`, so keep it installed.

## Commit & Pull Request Guidelines
- Follow Conventional Commits (`feat:`, `fix:`, `chore:`) as seen in the history.
- Keep each commit focused on a single logical change (one cluster or one module tweak).
- Pull requests should summarise scope, list affected clusters/modules, and attach the latest Terraform plan snippet plus YAML validation results.
- Link GitLab issues when relevant, call out any manual PAN-OS commits required, and verify secrets stay in environment variables (`GITLAB_PROJECT_ID`, `PANOS_API_KEY`, etc.).

## Security & Configuration Tips
Store credentials in shells or CI variables, never in files. The commit helper defaults to per-admin partial commits—leave that in place to avoid clobbering other operators. Rotate tokens when access changes and trim plan logs before sharing to avoid leaking sensitive objects.
