package repository

import (
	"context"
	"fmt"
	"log/slog"
	"os"
	"os/exec"
	"regexp"
	"strings"
	"time"

	"github.com/xanzy/go-gitlab"
)

type GitLabRepository struct {
	client     *gitlab.Client
	token      string
	projectID  string
	baseBranch string
	repoURL    string
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
		token:      token,
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

	// Set permissions to owner only
	if err := os.Chmod(tempDir, 0700); err != nil {
		os.RemoveAll(tempDir)
		return "", fmt.Errorf("failed to set temp dir permissions: %w", err)
	}

	// Setup cleanup on error
	defer func() {
		if err != nil {
			r.cleanupTempDir(tempDir)
		}
	}()

	// Create a secure credential helper script
	credScript, err := r.createCredentialScript()
	if err != nil {
		return "", fmt.Errorf("failed to create credential script: %w", err)
	}
	defer os.Remove(credScript)

	// Use credential helper instead of embedding token
	cmd := exec.CommandContext(ctx, "git", "clone",
		"--branch", r.baseBranch,
		"--depth", "1",
		"--config", "credential.helper="+credScript,
		r.repoURL, tempDir)

	if output, err := cmd.CombinedOutput(); err != nil {
		return "", fmt.Errorf("git clone failed: %w: %s", err, output)
	}

	slog.Info("cloned repository", "path", tempDir, "branch", r.baseBranch)
	return tempDir, nil
}

// CreateBranch creates new branch from current HEAD
func (r *GitLabRepository) CreateBranch(ctx context.Context, repoPath, branchName string) error {
	// Validate branch name
	if !r.isValidBranchName(branchName) {
		return fmt.Errorf("invalid branch name: %s", branchName)
	}

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

	// Check if there are changes to commit
	statusCmd := exec.CommandContext(ctx, "git", "status", "--porcelain")
	statusCmd.Dir = repoPath
	output, err := statusCmd.Output()
	if err != nil {
		return fmt.Errorf("git status failed: %w", err)
	}

	// If no changes, skip commit
	if strings.TrimSpace(string(output)) == "" {
		slog.Info("no changes to commit")
		return nil
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
	// Create a secure credential helper script
	credScript, err := r.createCredentialScript()
	if err != nil {
		return fmt.Errorf("failed to create credential script: %w", err)
	}
	defer os.Remove(credScript)

	// Use credential helper instead of embedding token
	cmd := exec.CommandContext(ctx, "git", "push",
		"--config", "credential.helper="+credScript,
		"-u", "origin", branchName)
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
		Title:              gitlab.String(title),
		Description:        gitlab.String(description),
		SourceBranch:       gitlab.String(sourceBranch),
		TargetBranch:       gitlab.String(r.baseBranch),
		RemoveSourceBranch: gitlab.Bool(true),
		Squash:             gitlab.Bool(true),
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
	return r.cleanupTempDir(repoPath)
}

// cleanupTempDir removes temp directory with retry
func (r *GitLabRepository) cleanupTempDir(repoPath string) error {
	var err error
	for i := 0; i < 3; i++ {
		err = os.RemoveAll(repoPath)
		if err == nil {
			return nil
		}
		// Wait before retry
		time.Sleep(100 * time.Millisecond)
	}
	if err != nil {
		slog.Warn("failed to cleanup temp dir after retries", "path", repoPath, "error", err)
		return fmt.Errorf("failed to cleanup temp dir: %w", err)
	}
	return nil
}

// createCredentialScript creates a temporary git credential helper script
func (r *GitLabRepository) createCredentialScript() (string, error) {
	script := fmt.Sprintf(`#!/bin/sh
echo "username=oauth2"
echo "password=%s"
`, r.token)

	// Create temp file for script
	tmpFile, err := os.CreateTemp("", "git-cred-*.sh")
	if err != nil {
		return "", fmt.Errorf("failed to create temp script: %w", err)
	}
	defer tmpFile.Close()

	// Set permissions to owner only
	if err := os.Chmod(tmpFile.Name(), 0700); err != nil {
		os.Remove(tmpFile.Name())
		return "", fmt.Errorf("failed to set script permissions: %w", err)
	}

	// Write script content
	if _, err := tmpFile.WriteString(script); err != nil {
		os.Remove(tmpFile.Name())
		return "", fmt.Errorf("failed to write script: %w", err)
	}

	return tmpFile.Name(), nil
}

// isValidBranchName validates git branch name
func (r *GitLabRepository) isValidBranchName(name string) bool {
	// Git branch name rules:
	// - Cannot start with hyphen
	// - Cannot contain spaces
	// - Cannot contain ..
	// - Cannot end with .lock
	// - Cannot contain problematic characters

	// Check for empty or too long names
	if len(name) == 0 || len(name) > 255 {
		return false
	}

	// Regex for valid branch names
	validBranchName := regexp.MustCompile(`^[a-zA-Z0-9._/-]+$`)

	// Additional checks
	if strings.HasPrefix(name, "-") {
		return false
	}
	if strings.Contains(name, "..") {
		return false
	}
	if strings.HasSuffix(name, ".lock") {
		return false
	}
	if strings.Contains(name, "@{") {
		return false
	}

	return validBranchName.MatchString(name)
}
