# SOAR Webhook Service: System Architecture

The SOAR Webhook Service is a Go-based microservice designed to automate the updating of firewall blocklists in response to security alerts originating from SOAR (Security Orchestration, Automation, and Response) platforms. It integrates with a GitOps workflow where firewall configurations are managed as YAML files in a GitLab repository.

## 1. Component Diagram (Text-based)

```mermaid
graph TD
    A[SOAR Platform] -- HTTP POST --> B(Webhook Service);

    subgraph Webhook Service
        B -- Handles Request --> C(HTTP Handler);
        C -- Processes Alert --> D(Alert Processor);
        D -- Modifies YAML --> E(YAML Processor);
        D -- Git Operations --> F(GitLab Repository Client);
    end

    F -- Pushes Code --> G[GitLab Repository];
    G -- Triggers --> H(GitLab CI/CD Pipeline);
    H -- Applies Changes --> I[Firewall Management System];
    I -- Updates --> J[Firewall Devices (e.g., PAN-OS)];
```

### Components Description:

-   **SOAR Platform**: The source of security alerts, which sends an HTTP POST request to the Webhook Service upon detecting a threat.
-   **Webhook Service**: The core application that receives, processes, and acts upon SOAR alerts.
    -   **HTTP Handler (`internal/handler/webhook.go`)**: Listens for incoming HTTP POST requests, parses the payload, and routes it for processing. Also provides health check endpoints.
    -   **Alert Processor (`internal/service/processor.go`)**: Orchestrates the workflow for processing a security alert. It clones the repository, updates the YAML configuration, commits changes, and creates a Merge Request.
    -   **YAML Processor (`internal/service/yaml_processor.go`)**: Specifically designed to modify the YAML configuration files. It adds new IP addresses to designated blocklists within the YAML structure, preserving formatting.
    -   **GitLab Repository Client (`internal/repository/gitlab.go`)**: Abstracts Git and GitLab API interactions, handling cloning, branching, committing, pushing, and Merge Request creation.
-   **GitLab Repository**: The central version-controlled repository where firewall configurations are stored as YAML files.
-   **GitLab CI/CD Pipeline**: Automated pipeline triggered by new Merge Requests. It validates the changes, generates a Terraform plan, and applies the changes to the firewall.
-   **Firewall Management System**: (e.g., Terraform with PAN-OS provider) Interprets the updated configuration and applies it to the actual firewall devices.
-   **Firewall Devices**: (e.g., Palo Alto Networks NGFW) The hardware or virtual appliances where the security policies are enforced.

## 2. Data Flow

1.  A SOAR platform generates an alert for a detected threat (e.g., malicious IP).
2.  The SOAR platform sends an HTTP POST request (webhook) containing the alert details to the running Webhook Service.
3.  The **HTTP Handler** receives the request and extracts relevant information, such as the malicious IP address.
4.  The **Alert Processor** initiates a series of Git operations via the **GitLab Repository Client**:
    *   It clones the firewall configuration repository to a temporary local directory.
    *   Creates a new Git branch for the proposed changes.
    *   Invokes the **YAML Processor** to add the malicious IP to the appropriate blocklist section within the `clusters/<cluster>/objects.yaml` file.
    *   Commits the updated YAML file to the new branch.
    *   Pushes the new branch to the remote GitLab repository.
    *   Creates a Merge Request in GitLab to propose merging the new branch into the main configuration branch.
5.  The creation of the Merge Request triggers a **GitLab CI/CD Pipeline**.
6.  The CI/CD pipeline performs validation, Terraform planning, and then, upon approval (manual or automatic), applies the Terraform configuration.
7.  The Terraform apply operation, utilizing the appropriate firewall provider (e.g., PAN-OS provider), communicates with the **Firewall Management System** (e.g., Panorama, Check Point Management Server).
8.  The Firewall Management System pushes the updated configuration, including the new blocklist entry, to the target **Firewall Devices**.

## 3. Deployment Architecture

The SOAR Webhook Service is designed for containerized deployment, typically orchestrated by Kubernetes or similar platforms.

-   **Containerization**: The service is packaged into a Docker image using a multi-stage `Dockerfile`.
    *   Build stage: Uses `golang:1.23-alpine` for building the Go application.
    *   Runtime stage: Uses a minimal `alpine:latest` base image for a small, secure deployment footprint.
    *   Security: The container runs as a non-root user (UID 1001) and defines a health check (`/health` endpoint).
-   **Orchestration (Helm Chart)**: A Helm chart is provided for easy deployment and management on Kubernetes.
    *   **Replicas**: Configured for 2 replicas by default, ensuring high availability and load balancing.
    *   **Service**: A `ClusterIP` service exposes the webhook handler internally within the Kubernetes cluster. An Ingress controller would typically expose this to the internet.
    *   **Resource Management**: Pods have defined CPU and memory limits (e.g., 100m CPU, 128Mi memory) to prevent resource exhaustion and ensure stable operation.
    *   **Security Context**: Pods are configured with security contexts that enforce non-root execution and drop all Linux capabilities, adhering to security best practices.
-   **Configuration**: All operational parameters are injected into the running containers via environment variables. This allows for dynamic configuration without rebuilding the Docker image.
    *   **Required**: `GITLAB_URL`, `GITLAB_TOKEN`, `GITLAB_PROJECT_ID`, `REPO_CLONE_URL` (from project's CLAUDE.md)
    *   **Service Specific**: `GITLAB_BRANCH`, `YAML_FILE_PATH`, `OBJECT_PATH`, `SERVER_PORT`.

## 4. Security Considerations

-   **Secrets Management**: GitLab tokens and other sensitive credentials are never embedded in the code or Docker image. They are provided at runtime via environment variables, typically managed by Kubernetes Secrets or a similar secrets management solution.
-   **Least Privilege**: The GitLab token used by the service should be scoped with the minimum necessary permissions required for its operations (repository read/write, branch creation, MR creation).
-   **Input Validation**: Strict validation is applied to all incoming webhook payloads and internal data used in shell commands to prevent injection attacks (e.g., `git` command injection).
-   **Container Hardening**: The Docker image is built with security in mind, running as a non-root user and dropping unnecessary Linux capabilities.
-   **Temporary File Handling**: All temporary Git clones and other temporary files are handled securely and cleaned up promptly to prevent sensitive data exposure.
-   **Future Enhancements**: Implement `WEBHOOK_SECRET` validation to authenticate incoming SOAR alerts.
