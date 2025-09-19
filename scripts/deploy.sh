#!/bin/bash
# Deployment script for local development and testing

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TERRAFORM_DIR="$PROJECT_ROOT/terraform"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
CLUSTER_NAME=""
ACTION="plan"
AUTO_APPROVE=false
DRY_RUN=false

usage() {
    echo "Usage: $0 -c CLUSTER_NAME [-a ACTION] [-y] [-d]"
    echo ""
    echo "Options:"
    echo "  -c, --cluster     Cluster name (required)"
    echo "  -a, --action      Action to perform: plan, apply, destroy (default: plan)"
    echo "  -y, --auto-approve Auto-approve changes (for apply/destroy)"
    echo "  -d, --dry-run     Dry run mode (plan only)"
    echo "  -h, --help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 -c development                    # Plan changes for development cluster"
    echo "  $0 -c production -a apply -y         # Apply changes to production cluster"
    echo "  $0 -c development -a destroy -y      # Destroy development cluster resources"
    exit 1
}

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -c|--cluster)
            CLUSTER_NAME="$2"
            shift 2
            ;;
        -a|--action)
            ACTION="$2"
            shift 2
            ;;
        -y|--auto-approve)
            AUTO_APPROVE=true
            shift
            ;;
        -d|--dry-run)
            DRY_RUN=true
            ACTION="plan"
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            error "Unknown option: $1"
            usage
            ;;
    esac
done

# Validate required parameters
if [[ -z "$CLUSTER_NAME" ]]; then
    error "Cluster name is required"
    usage
fi

# Validate action
if [[ ! "$ACTION" =~ ^(plan|apply|destroy)$ ]]; then
    error "Invalid action: $ACTION. Must be one of: plan, apply, destroy"
    exit 1
fi

# Check if cluster configuration exists
CLUSTER_DIR="$PROJECT_ROOT/clusters/$CLUSTER_NAME"
if [[ ! -d "$CLUSTER_DIR" ]]; then
    error "Cluster directory not found: $CLUSTER_DIR"
    exit 1
fi

if [[ ! -f "$CLUSTER_DIR/cluster-config.yaml" ]]; then
    error "Cluster configuration not found: $CLUSTER_DIR/cluster-config.yaml"
    exit 1
fi

if [[ ! -f "$CLUSTER_DIR/firewall-rules.yaml" ]]; then
    error "Firewall rules not found: $CLUSTER_DIR/firewall-rules.yaml"
    exit 1
fi

log "Starting deployment for cluster: $CLUSTER_NAME"
log "Action: $ACTION"
log "Auto-approve: $AUTO_APPROVE"
log "Dry run: $DRY_RUN"

# Validate YAML configurations
log "Validating YAML configurations..."
cd "$PROJECT_ROOT"
if ! python3 scripts/validate_yaml.py; then
    error "YAML validation failed"
    exit 1
fi
success "YAML validation passed"

# Change to Terraform directory
cd "$TERRAFORM_DIR"

# Check if Terraform is installed
if ! command -v terraform &> /dev/null; then
    error "Terraform is not installed"
    exit 1
fi

# Initialize Terraform
log "Initializing Terraform..."
if ! terraform init; then
    error "Terraform initialization failed"
    exit 1
fi

# Validate Terraform configuration
log "Validating Terraform configuration..."
if ! terraform validate; then
    error "Terraform validation failed"
    exit 1
fi

# Format check
log "Checking Terraform formatting..."
if ! terraform fmt -check -recursive; then
    warning "Terraform files are not properly formatted"
    log "Running terraform fmt..."
    terraform fmt -recursive
fi

# Execute the requested action
case $ACTION in
    plan)
        log "Creating Terraform plan for cluster: $CLUSTER_NAME"
        PLAN_FILE="plan-$CLUSTER_NAME.tfplan"
        
        if terraform plan -var="cluster_name=$CLUSTER_NAME" -out="$PLAN_FILE"; then
            success "Terraform plan completed successfully"
            log "Plan file saved as: $PLAN_FILE"
            
            # Show plan summary
            log "Plan summary:"
            terraform show -json "$PLAN_FILE" | jq -r '.planned_values.outputs // {}'
        else
            error "Terraform plan failed"
            exit 1
        fi
        ;;
        
    apply)
        PLAN_FILE="plan-$CLUSTER_NAME.tfplan"
        
        # Create plan first if it doesn't exist
        if [[ ! -f "$PLAN_FILE" ]]; then
            log "Creating Terraform plan first..."
            if ! terraform plan -var="cluster_name=$CLUSTER_NAME" -out="$PLAN_FILE"; then
                error "Terraform plan failed"
                exit 1
            fi
        fi
        
        # Apply the plan
        log "Applying Terraform plan for cluster: $CLUSTER_NAME"
        
        APPLY_ARGS=""
        if [[ "$AUTO_APPROVE" == "true" ]]; then
            APPLY_ARGS="-auto-approve"
        fi
        
        if [[ "$DRY_RUN" == "true" ]]; then
            log "Dry run mode - skipping actual apply"
            success "Dry run completed"
        else
            if terraform apply $APPLY_ARGS "$PLAN_FILE"; then
                success "Terraform apply completed successfully"
                
                # Show outputs
                log "Deployment outputs:"
                terraform output -json
            else
                error "Terraform apply failed"
                exit 1
            fi
        fi
        ;;
        
    destroy)
        warning "This will destroy all resources for cluster: $CLUSTER_NAME"
        
        if [[ "$AUTO_APPROVE" != "true" ]]; then
            read -p "Are you sure you want to continue? (yes/no): " confirm
            if [[ "$confirm" != "yes" ]]; then
                log "Destroy cancelled"
                exit 0
            fi
        fi
        
        log "Destroying resources for cluster: $CLUSTER_NAME"
        
        DESTROY_ARGS="-var=cluster_name=$CLUSTER_NAME"
        if [[ "$AUTO_APPROVE" == "true" ]]; then
            DESTROY_ARGS="$DESTROY_ARGS -auto-approve"
        fi
        
        if [[ "$DRY_RUN" == "true" ]]; then
            log "Dry run mode - showing destroy plan"
            terraform plan -destroy $DESTROY_ARGS
            success "Dry run completed"
        else
            if terraform destroy $DESTROY_ARGS; then
                success "Resources destroyed successfully"
            else
                error "Terraform destroy failed"
                exit 1
            fi
        fi
        ;;
esac

success "Deployment script completed successfully"
