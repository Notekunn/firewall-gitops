# Phase 02: GitLab API Integration

**Priority:** High
**Status:** Pending
**Dependencies:** Phase 01

## Overview

Implement GitLab repository operations: clone/pull branch, create commits, push changes, create merge requests via GitLab API.

## Key Insights

- Use go-gitlab SDK for API operations
- Work with local git clone for YAML manipulation
- Create MR instead of direct push (per requirements)
- Branch strategy: create feature branch per alert, MR to main

## Requirements

### Functional
- Clone repository to temp directory
- Pull latest from configured branch
- Create new branch for each webhook event
- Commit YAML changes with descriptive message
- Push branch to remote
- Create merge request via API
- Cleanup temp directory after processing

### Non-Functional
- Handle concurrent webhook requests (separate temp dirs)
- Retry on transient failures
- Proper error context for debugging

## Architecture

**Repository Pattern:**
```
Service (Phase 03) → GitLabRepository → go-gitlab SDK + git commands
                                     ↓
                              Local Git Clone (temp dir)
```

## Related Code Files

**Create:**
- `internal/repository/gitlab.go` - GitLab repository operations
- `internal/repository/gitlab_test.go` - Unit tests (mocked)

**Modify:**
- `go.mod` - Add go-gitlab dependency

## Implementation Steps

### 1. Add Dependencies
```bash
go get github.com/xanzy/go-gitlab@latest
go get github.com/go-git/go-git/v5@latest  # Optional: pure Go git ops
```

**Alternative:** Use os/exec for git commands (simpler, requires git binary)

### 2. Implement GitLab Repository
**File:** `internal/repository/gitlab.go`

```go
package repository

import (
    "context"
    "fmt"
    "log/slog"
    "os"
    "os/exec"
    "path/filepath"
    "strings"

    "github.com/xanzy/go-gitlab"
)

type GitLabRepository struct {
    client    *gitlab.Client
    projectID string
    baseBranch string
    repoURL   string
}

func NewGitLabRepository(url, token, projectID, branch string) (*GitLabRepository, error) {
    client, err := gitlab.NewClient(token, gitlab.WithBaseURL(url))
    if err != nil {
        return nil, fmt.Errorf("failed to create gitlab client: %w", err)
    }

    // Get project to validate access and construct git URL
    project, _, err := client.Projects.GetProject(projectID, nil)
    if err != nil {
        return nil, fmt.Errorf("failed to get project: %w", err)
    }

    return &GitLabRepository{
        client:     client,
        projectID:  projectID,
        baseBranch: branch,
        repoURL:    project.HTTPURLToRepo,
    }, nil
}

// CloneToTemp clones repository to temp directory and returns path
func (r *GitLabRepository) CloneToTemp(ctx context.Context) (string, error) {
    tempDir, err := os.MkdirTemp("", "webhook-soar-*")
    if err != nil {
        return "", fmt.Errorf("failed to create temp dir: %w", err)
    }

    // Inject token into URL for authentication
    authURL := r.injectToken(r.repoURL)

    cmd := exec.CommandContext(ctx, "git", "clone", "--branch", r.baseBranch, authURL, tempDir)
    if output, err := cmd.CombinedOutput(); err != nil {
        os.RemoveAll(tempDir)
        return "", fmt.Errorf("git clone failed: %w: %s", err, output)
    }

    slog.Info("cloned repository", "path", tempDir, "branch", r.baseBranch)
    return tempDir, nil
}

// CreateBranch creates new branch from current HEAD
func (r *GitLabRepository) CreateBranch(ctx context.Context, repoPath, branchName string) error {
    cmd := exec.CommandContext(ctx, "git", "checkout", "-b", branchName)
    cmd.Dir = repoPath
    if output, err := cmd.CombinedOutput(); err != nil {
        return fmt.Errorf("git checkout -b failed: %w: %s", err, output)
    }
    return nil
}

// CommitChanges commits all changes with message
func (r *GitLabRepository) CommitChanges(ctx context.Context, repoPath, message string) error {
    // Stage all changes
    addCmd := exec.CommandContext(ctx, "git", "add", ".")
    addCmd.Dir = repoPath
    if output, err := addCmd.CombinedOutput(); err != nil {
        return fmt.Errorf("git add failed: %w: %s", err, output)
    }

    // Commit with message
    commitCmd := exec.CommandContext(ctx, "git", "commit", "-m", message)
    commitCmd.Dir = repoPath
    if output, err := commitCmd.CombinedOutput(); err != nil {
        return fmt.Errorf("git commit failed: %w: %s", err, output)
    }

    return nil
}

// PushBranch pushes branch to remote
func (r *GitLabRepository) PushBranch(ctx context.Context, repoPath, branchName string) error {
    authURL := r.injectToken(r.repoURL)

    cmd := exec.CommandContext(ctx, "git", "push", "-u", authURL, branchName)
    cmd.Dir = repoPath
    if output, err := cmd.CombinedOutput(); err != nil {
        return fmt.Errorf("git push failed: %w: %s", err, output)
    }

    slog.Info("pushed branch", "branch", branchName)
    return nil
}

// CreateMergeRequest creates MR from branch to base branch
func (r *GitLabRepository) CreateMergeRequest(ctx context.Context, sourceBranch, title, description string) (int, error) {
    opts := &gitlab.CreateMergeRequestOptions{
        Title:        gitlab.String(title),
        Description:  gitlab.String(description),
        SourceBranch: gitlab.String(sourceBranch),
        TargetBranch: gitlab.String(r.baseBranch),
    }

    mr, _, err := r.client.MergeRequests.CreateMergeRequest(r.projectID, opts)
    if err != nil {
        return 0, fmt.Errorf("failed to create merge request: %w", err)
    }

    slog.Info("created merge request",
        "mr_iid", mr.IID,
        "source", sourceBranch,
        "target", r.baseBranch,
        "url", mr.WebURL)

    return mr.IID, nil
}

// Cleanup removes temp directory
func (r *GitLabRepository) Cleanup(repoPath string) error {
    return os.RemoveAll(repoPath)
}

// injectToken adds token to git URL for authentication
func (r *GitLabRepository) injectToken(url string) string {
    // Convert https://gitlab.com/user/repo.git
    // to https://oauth2:TOKEN@gitlab.com/user/repo.git
    return strings.Replace(url, "https://", fmt.Sprintf("https://oauth2:%s@", r.client.Token()), 1)
}
```

### 3. Write Tests
**File:** `internal/repository/gitlab_test.go`

Mock GitLab API responses, test:
- Successful repository clone
- Branch creation
- Commit operations
- Push to remote
- MR creation
- Error handling for each operation

### 4. Update Main
**File:** `cmd/webhook/main.go`

Add repository initialization:
```go
repo, err := repository.NewGitLabRepository(
    cfg.GitLabURL,
    cfg.GitLabToken,
    cfg.GitLabProjectID,
    cfg.GitLabBranch,
)
if err != nil {
    slog.Error("failed to initialize gitlab repository", "error", err)
    os.Exit(1)
}
```

## Todo List

- [ ] Add go-gitlab dependency
- [ ] Implement GitLabRepository struct
- [ ] Implement CloneToTemp() with git clone
- [ ] Implement CreateBranch() for feature branches
- [ ] Implement CommitChanges() with git add/commit
- [ ] Implement PushBranch() with authentication
- [ ] Implement CreateMergeRequest() via API
- [ ] Implement Cleanup() for temp directories
- [ ] Write unit tests with mocked API
- [ ] Test token injection for git URLs
- [ ] Verify error wrapping and context

## Success Criteria

- Clone repository to temp directory
- Create branch with unique name
- Commit and push changes
- Create MR successfully
- Cleanup temp directory after processing
- All errors properly wrapped with context

## Risk Assessment

**Medium risk** - Git operations, authentication, temp file management.

**Mitigations:**
- Use context for cancellation/timeout
- Wrap all errors with operation context
- Ensure temp directory cleanup (defer)
- Validate GitLab token has required permissions (api, write_repository)

## Security Considerations

- Never log git URLs with embedded tokens
- Secure temp directory permissions (0700)
- Clean up temp directories even on error (defer)
- Validate project access before operations
- Use oauth2 token auth (not basic auth)

## Next Steps

After phase 02:
- Phase 03: YAML parsing and IP list management
- Need YAML library: gopkg.in/yaml.v3
