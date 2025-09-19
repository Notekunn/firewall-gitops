# Firewall GitOps Project

This project provides a GitOps approach to managing firewall configurations using Terraform modules. Network developers can define firewall rules using simple YAML configuration files, which are then automatically converted to Terraform and applied via GitLab CI/CD.

## 🚀 Features

- **YAML-based Configuration**: Simple, human-readable firewall rule definitions
- **GitOps Workflow**: Version-controlled infrastructure with automated deployments
- **Multi-Environment Support**: Separate configurations for dev, staging, and production
- **Automated Validation**: YAML schema validation and Terraform plan checks
- **Security Scanning**: Built-in security best practices validation
- **Approval Workflows**: Manual approval gates for production changes

## 🔥 Supported Firewalls

- ✅ **Palo Alto Networks (PAN-OS)** - Full support for Panorama and standalone NGFW
- 🚧 **Fortinet** (planned for future release)

## 📁 Project Structure

```
firewall-gitops/
├── clusters/                    # Cluster-specific configurations
│   └── example/
│       ├── cluster.yaml         # Cluster metadata and firewall settings
│       └── rules.yaml           # Firewall rules and address/service objects
├── modules/                     # Terraform modules
│   ├── palo-alto/              # Palo Alto Networks module
│   │   ├── main.tf
│   │   └── variables.tf
│   └── shared/                 # Shared modules and utilities
├── terraform/                  # Main Terraform configuration
│   ├── main.tf                 # YAML parser and module calls
│   └── variables.tf
├── scripts/                    # Helper scripts
│   ├── validate_yaml.py        # YAML validation script
│   └── deploy.sh              # Local deployment script
├── schemas/                    # JSON schemas for validation
│   ├── cluster.schema.json     # Cluster configuration schema
│   ├── rules.schema.json       # Rules configuration schema
│   └── README.md              # Schema documentation
├── docs/                       # Documentation
│   ├── configuration.md        # Configuration guide
│   └── getting-started.md     # Getting started guide
├── requirements.txt            # Python dependencies
└── README.md
```

## 🚀 Quick Start

### 1. Create Your First Cluster

```bash
# Create cluster directory
mkdir -p clusters/my-cluster

# Copy example configurations
cp clusters/example/* clusters/my-cluster/

# Edit configurations for your environment
vim clusters/my-cluster/cluster.yaml
vim clusters/my-cluster/rules.yaml
```

### 2. Configure GitLab Access

```bash
# Set up GitLab environment variables for state management
export GITLAB_PROJECT_ID="your-project-id"
export GITLAB_TOKEN="your-personal-access-token" 
export GITLAB_API_URL="https://gitlab.com/api/v4"
export GITLAB_USERNAME="your-gitlab-username"
```

### 3. Validate Your Configuration

```bash
# Install dependencies (use virtual environment)
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Validate YAML configuration
python scripts/validate_yaml.py
```

### 4. Deploy Changes

```bash
# Local deployment (development)
./scripts/deploy.sh -c my-cluster -a plan

# Apply changes
./scripts/deploy.sh -c my-cluster -a apply -y
```

### 5. GitOps Workflow

1. **Create a feature branch** for your changes
2. **Modify cluster configurations** in YAML files
3. **Commit and push** to GitLab
4. **Create a merge request** - pipeline will validate automatically
5. **Merge to main** - changes deploy automatically (with approval for production)

## 📖 Documentation

- **[Getting Started Guide](docs/getting-started.md)** - Detailed setup and usage instructions
- **[Configuration Guide](docs/configuration.md)** - Complete YAML configuration reference
- **Example Configurations** - See `clusters/` directory for working examples

## 🛠️ Requirements

### Software Requirements
- **Terraform** >= 1.0
- **Python** >= 3.8 (for validation scripts)
- **Git** for version control
- **GitLab** for CI/CD pipeline

### Firewall Access
- **Palo Alto Networks**: API access to Panorama or NGFW
- **Permissions**: Device group management (Panorama) or configuration management (NGFW)

### Provider Versions
- `paloaltonetworks/panos` >= 2.0.5

## 🔧 Configuration Examples

### Complete Rules Configuration

```yaml
# clusters/my-cluster/rules.yaml
addresses:
  - name: 'web-server'
    ip_netmask: '192.168.1.100/32'
    description: 'Web server address'
    tags: ['web', 'server']
  - name: 'app-servers'
    ip_netmask: '10.1.1.0/24'
    description: 'Application server subnet'
    tags: ['app', 'backend']

services:
  - name: 'web-service'
    type: 'tcp'
    destination_port: '80'
    source_port: '1024-65535'
    description: 'Web service HTTP'
    tags: ['web', 'http']
  - name: 'https-service'
    type: 'tcp'
    destination_port: '443'
    source_port: '1024-65535'
    description: 'Web service HTTPS'
    tags: ['web', 'https']

rules:
  web_access:
    description: 'Allow web access rules'
    rules:
      - name: 'allow-web-traffic'
        description: 'Allow HTTP traffic to web server'
        source_zones: ['trust']
        destination_zones: ['dmz']
        source_addresses: ['any']
        destination_addresses: ['web-server']
        applications: ['web-browsing']
        services: ['web-service']
        action: 'allow'
        log_end: true
      - name: 'allow-https-traffic'
        description: 'Allow HTTPS traffic to web server'
        source_zones: ['trust']
        destination_zones: ['dmz']
        source_addresses: ['any']
        destination_addresses: ['web-server']
        applications: ['ssl']
        services: ['https-service']
        action: 'allow'
        log_end: true
```

### Address Object Types

The schema supports multiple address object types based on Terraform variables:

```yaml
addresses:
  # IP with netmask
  - name: 'subnet-example'
    ip_netmask: '192.168.1.0/24'
    description: 'Network subnet'
    
  # IP range
  - name: 'range-example'
    ip_range: '192.168.1.10-192.168.1.20'
    description: 'IP address range'
    
  # FQDN
  - name: 'domain-example'
    fqdn: 'example.com'
    description: 'Domain name'
    
  # IP with wildcard mask
  - name: 'wildcard-example'
    ip_wildcard: '192.168.1.0/0.0.0.255'
    description: 'Wildcard address'
```

## 🔒 Security Features

- **JSON Schema Validation**: Comprehensive validation using auto-generated schemas from Terraform variables
- **Type Safety**: Strict type checking for all configuration fields with proper null handling
- **Input Validation**: Regex patterns for IP addresses, ports, FQDNs, and other network objects
- **Configuration Consistency**: Ensures all required fields are present and valid
- **Audit Trail**: Full Git history of all configuration changes
- **Principle of Least Privilege**: Encourages minimal access patterns

## 📋 Schema Features

The project includes comprehensive JSON schemas that are automatically generated from Terraform module variables:

- **Address Objects**: Support for `ip_netmask`, `ip_range`, `ip_wildcard`, and `fqdn` with validation
- **Service Objects**: TCP/UDP services with port validation and source/destination port support
- **Security Rules**: Complete rule definitions with optional fields and security profiles
- **Automatic Validation**: All YAML files are validated against schemas before deployment

## 🚦 Pipeline Stages

The GitLab CI pipeline includes:

1. **Validate** - YAML syntax and JSON schema validation using `validate_yaml.py`
2. **Plan** - Terraform plan for changed clusters
3. **Apply** - Automated deployment (with approval for production)
4. **Security Scan** - Security best practices validation
5. **Cleanup** - Cleanup old plan files and artifacts

## 🛠️ Development

### Schema Regeneration

The JSON schemas are automatically generated from Terraform module variables. To regenerate schemas after updating Terraform variables:

```bash
# The schemas are based on these Terraform variables:
# - firewall_addresses (modules/palo-alto/variables.tf)
# - firewall_services (modules/palo-alto/variables.tf)  
# - firewall_rules (modules/palo-alto/variables.tf)

# Validate updated schemas
source venv/bin/activate
python scripts/validate_yaml.py
```

### State Management

The project uses **GitLab managed Terraform state** with cluster-specific state names to enable independent management of multiple firewall clusters:

- **All Environments**: Uses GitLab managed Terraform state with naming pattern `firewall-gitops-{cluster_name}`
- **State Storage**: Terraform state is stored securely in GitLab's infrastructure
- **Remote Backend**: HTTP backend with GitLab's Terraform state API

Each cluster maintains its own state in GitLab, providing:
- **Centralized Management**: All state stored securely in GitLab
- **Independent Deployments**: Clusters deploy without conflicts
- **Parallel Execution**: Multiple clusters can be deployed simultaneously
- **State Locking**: GitLab provides automatic state locking
- **Access Control**: GitLab project permissions control state access
- **Backup & Recovery**: GitLab handles state backup and recovery

#### Local Development Setup

For local development, you need to configure GitLab access:

```bash
# Required environment variables for local development
export GITLAB_TOKEN="your-personal-access-token"
export GITLAB_API_URL="https://gitlab.com/api/v4"
export GITLAB_USERNAME="your-gitlab-username"

# Deploy using GitLab managed state
./scripts/deploy.sh -c development -a plan
```

**Personal Access Token Requirements:**
- Scope: `api` (for Terraform state management)
- Role: `Developer` or higher on the project
- Find your project ID in GitLab: Project → Settings → General → Project ID

### PAN-OS Provider Configuration

The CI/CD pipeline requires the following environment variables for PAN-OS connectivity:

**Required Variables:**
- `PANOS_HOSTNAME` - Firewall or Panorama hostname/IP
- `PANOS_USERNAME` - Username for authentication
- `PANOS_PASSWORD` - Password for authentication (or use API key)

**Optional Variables:**
- `PANOS_API_KEY` - API key (alternative to username/password)
- `PANOS_PROTOCOL` - Protocol to use (default: `https`)
- `PANOS_PORT` - Port number (default: `443`)
- `PANOS_TIMEOUT` - Connection timeout in seconds (default: `10`)
- `PANOS_SKIP_VERIFY_CERTIFICATE` - Skip SSL verification (default: `true`)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests and documentation
5. Submit a merge request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

- **Issues**: Create an issue in GitLab for bugs or feature requests
- **Documentation**: Check the `docs/` directory for detailed guides
- **Examples**: Reference the `clusters/` directory for working configurations


