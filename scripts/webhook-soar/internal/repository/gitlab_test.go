package repository

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
)

// Helper function to create a test repository with mocked client
func createTestRepo(t *testing.T) (*GitLabRepository, string, func()) {
	// Create a temporary directory for the test
	tempDir, err := os.MkdirTemp("", "webhook-soar-test-*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}

	// Initialize a git repository in temp dir
	gitDir := filepath.Join(tempDir, "test-repo")
	if err := os.MkdirAll(gitDir, 0755); err != nil {
		os.RemoveAll(tempDir)
		t.Fatalf("Failed to create git dir: %v", err)
	}

	// Initialize git repo and create initial commit
	commands := [][]string{
		{"git", "init"},
		{"git", "config", "user.email", "test@example.com"},
		{"git", "config", "user.name", "Test User"},
		{"git", "checkout", "-b", "main"},
		{"touch", "test.yaml"},
		{"git", "add", "."},
		{"git", "commit", "-m", "Initial commit"},
	}

	for _, cmd := range commands {
		var c *exec.Cmd
		if len(cmd) == 2 && cmd[0] == "touch" {
			f, err := os.Create(filepath.Join(gitDir, cmd[1]))
			if err != nil {
				os.RemoveAll(tempDir)
				t.Fatalf("Failed to create test file: %v", err)
			}
			f.Close()
			continue
		}
		c = exec.Command(cmd[0], cmd[1:]...)
		c.Dir = gitDir
		if err := c.Run(); err != nil {
			os.RemoveAll(tempDir)
			t.Fatalf("Failed to run %v: %v", cmd, err)
		}
	}

	// Create repository instance (we'll mock the client for API calls)
	repo := &GitLabRepository{
		client:     nil, // Not used in these tests
		token:      "test-token",
		projectID:  "123",
		baseBranch: "main",
		repoURL:    "https://gitlab.com/test/repo.git",
	}

	cleanup := func() {
		os.RemoveAll(tempDir)
	}

	return repo, gitDir, cleanup
}

func TestGitLabRepository_Cleanup(t *testing.T) {
	// Create temp directory
	tempDir, err := os.MkdirTemp("", "webhook-soar-cleanup-test-*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}

	// Verify directory exists
	if _, err := os.Stat(tempDir); os.IsNotExist(err) {
		t.Fatalf("Temp directory was not created")
	}

	repo := &GitLabRepository{}
	err = repo.Cleanup(tempDir)
	assert.NoError(t, err)

	// Verify directory is removed
	if _, err := os.Stat(tempDir); !os.IsNotExist(err) {
		t.Errorf("Temp directory was not removed")
	}
}

func TestGitLabRepository_CreateBranch(t *testing.T) {
	repo, gitDir, cleanup := createTestRepo(t)
	defer cleanup()

	ctx := context.Background()
	branchName := "feature/test-branch"

	err := repo.CreateBranch(ctx, gitDir, branchName)
	assert.NoError(t, err)

	// Verify branch was created
	cmd := exec.CommandContext(ctx, "git", "branch", "--show-current")
	cmd.Dir = gitDir
	output, err := cmd.Output()
	if err != nil {
		t.Fatalf("Failed to get current branch: %v", err)
	}

	currentBranch := strings.TrimSpace(string(output))
	assert.Equal(t, branchName, currentBranch)
}

func TestGitLabRepository_CommitChanges(t *testing.T) {
	repo, gitDir, cleanup := createTestRepo(t)
	defer cleanup()

	ctx := context.Background()
	message := "Test commit message"

	// Create a new file
	testFile := filepath.Join(gitDir, "new-file.txt")
	err := os.WriteFile(testFile, []byte("test content"), 0644)
	assert.NoError(t, err)

	// Commit changes
	err = repo.CommitChanges(ctx, gitDir, message)
	assert.NoError(t, err)

	// Verify commit was created
	cmd := exec.CommandContext(ctx, "git", "log", "-1", "--pretty=format:%s")
	cmd.Dir = gitDir
	output, err := cmd.Output()
	if err != nil {
		t.Fatalf("Failed to get commit message: %v", err)
	}

	commitMessage := strings.TrimSpace(string(output))
	assert.Equal(t, message, commitMessage)
}

func TestGitLabRepository_CommitChanges_NoChanges(t *testing.T) {
	repo, gitDir, cleanup := createTestRepo(t)
	defer cleanup()

	ctx := context.Background()
	message := "Test commit message"

	// Try to commit without changes
	err := repo.CommitChanges(ctx, gitDir, message)
	assert.NoError(t, err)
}

func TestGitLabRepository_createCredentialScript(t *testing.T) {
	repo := &GitLabRepository{
		token: "test-token-123",
	}

	script, err := repo.createCredentialScript()
	if err != nil {
		t.Fatalf("Failed to create credential script: %v", err)
	}
	defer os.Remove(script)

	// Verify script exists
	if _, err := os.Stat(script); os.IsNotExist(err) {
		t.Error("Credential script was not created")
	}

	// Verify script content
	content, err := os.ReadFile(script)
	if err != nil {
		t.Fatalf("Failed to read script: %v", err)
	}

	contentStr := string(content)
	if !strings.Contains(contentStr, "echo \"username=oauth2\"") {
		t.Error("Script does not contain username")
	}
	if !strings.Contains(contentStr, "echo \"password=test-token-123\"") {
		t.Error("Script does not contain token")
	}
}

func TestGitLabRepository_isValidBranchName(t *testing.T) {
	tests := []struct {
		name  string
		valid bool
	}{
		{"feature/test", true},
		{"feature-123", true},
		{"release_v1.0", true},
		{"hotfix", true},
		{"-invalid", false},      // Starts with hyphen
		{"invalid name", false},  // Contains space
		{"invalid..name", false}, // Contains double dot
		{"invalid.lock", false},  // Ends with .lock
		{"invalid@{ref}", false}, // Contains @{
		{"", false},              // Empty
		{"a", true},              // Single character
		{"feature/feature/feature", true},
		{strings.Repeat("a", 300), false}, // Too long
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			repo := &GitLabRepository{}
			result := repo.isValidBranchName(tt.name)
			assert.Equal(t, tt.valid, result)
		})
	}
}

// Test error handling for git operations
func TestGitLabRepository_CreateBranch_Error(t *testing.T) {
	repo := &GitLabRepository{}
	ctx := context.Background()

	// Invalid directory should cause error
	err := repo.CreateBranch(ctx, "/nonexistent/path", "test-branch")
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "git checkout -b failed")
}

func TestGitLabRepository_CommitChanges_Error(t *testing.T) {
	repo := &GitLabRepository{}
	ctx := context.Background()

	// Invalid directory should cause error
	err := repo.CommitChanges(ctx, "/nonexistent/path", "test message")
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "git add failed")
}

func TestGitLabRepository_PushBranch_Error(t *testing.T) {
	repo := &GitLabRepository{}
	ctx := context.Background()

	// Invalid directory should cause error
	err := repo.PushBranch(ctx, "/nonexistent/path", "test-branch")
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "git push failed")
}
