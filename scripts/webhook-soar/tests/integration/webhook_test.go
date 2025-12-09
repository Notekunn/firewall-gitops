//go:build integration
// +build integration

package integration

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"firewall-gitops/webhook-soar/internal/config"
	"firewall-gitops/webhook-soar/internal/handler"
	"firewall-gitops/webhook-soar/internal/repository"
	"firewall-gitops/webhook-soar/internal/service"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestWebhookHandler_Integration(t *testing.T) {
	// Skip if not running integration tests
	if os.Getenv("INTEGRATION_TESTS") != "true" {
		t.Skip("Skipping integration tests. Set INTEGRATION_TESTS=true to run.")
	}

	// Setup test environment
	gitlabURL := os.Getenv("GITLAB_URL")
	gitlabToken := os.Getenv("GITLAB_TOKEN")
	gitlabProjectID := os.Getenv("GITLAB_PROJECT_ID")

	if gitlabURL == "" || gitlabToken == "" || gitlabProjectID == "" {
		t.Skip("Missing required environment variables: GITLAB_URL, GITLAB_TOKEN, GITLAB_PROJECT_ID")
	}

	// Create temporary YAML file for testing
	tempDir, err := os.MkdirTemp("", "webhook-soar-test-*")
	require.NoError(t, err)
	defer os.RemoveAll(tempDir)

	yamlPath := filepath.Join(tempDir, "test-objects.yaml")
	yamlContent := `
addresses:
  - name: existing-ip
    ip_netmask: 192.168.1.100/32
    description: "Already blocked IP"
`
	err = os.WriteFile(yamlPath, []byte(yamlContent), 0644)
	require.NoError(t, err)

	// Setup configuration
	cfg := &config.Config{
		GitLabURL:       gitlabURL,
		GitLabToken:     gitlabToken,
		GitLabProjectID: gitlabProjectID,
		GitLabBranch:    "main",
		YAMLFilePath:    yamlPath,
		ObjectPath:      "addresses",
		ServerPort:      "8080",
	}

	// Initialize real components
	repo, err := repository.NewGitLabRepository(
		cfg.GitLabURL,
		cfg.GitLabToken,
		cfg.GitLabProjectID,
		cfg.GitLabBranch,
	)
	require.NoError(t, err)

	yamlProc := service.NewYAMLProcessor(cfg.YAMLFilePath, cfg.ObjectPath)
	processor := service.NewProcessor(repo, yamlProc)
	webhookHandler := handler.NewWebhookHandler(processor)

	// Test data
	testIP := "10.0.0.100"
	testTicketID := "INTEGRATION-TEST-001"
	testReason := "Integration test IP blocking"

	// Perform the webhook request
	reqBody := map[string]interface{}{
		"ticket_id": testTicketID,
		"attacker": map[string]interface{}{
			"type":  "ip_v4",
			"value": testIP,
		},
		"reason": testReason,
	}

	body, _ := json.Marshal(reqBody)
	req := httptest.NewRequest("POST", "/webhook", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	// Execute request with timeout
	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()
	req = req.WithContext(ctx)

	webhookHandler.HandleWebhook(w, req)

	// Verify response
	assert.Equal(t, 200, w.Code)

	var resp handler.WebhookResponse
	err = json.Unmarshal(w.Body.Bytes(), &resp)
	require.NoError(t, err)

	assert.True(t, resp.Success)
	assert.Equal(t, "IP added to blocklist", resp.Message)
	assert.Greater(t, resp.MergeRequest, 0, "Merge request ID should be positive")

	t.Logf("Successfully created merge request: %d", resp.MergeRequest)

	// Verify the IP was actually added to the YAML
	// Clone the repo to check
	repoPath, err := repo.CloneToTemp(ctx)
	require.NoError(t, err)
	defer func() {
		if cleanupErr := repo.Cleanup(repoPath); cleanupErr != nil {
			t.Logf("Warning: failed to cleanup temp directory: %v", cleanupErr)
		}
	}()

	// Read the updated YAML content
	updatedYAMLPath := filepath.Join(repoPath, cfg.YAMLFilePath)
	content, err := os.ReadFile(updatedYAMLPath)
	require.NoError(t, err)

	assert.Contains(t, string(content), testIP, "IP should be added to YAML file")
	t.Logf("Verified IP %s was added to YAML file", testIP)
}

func TestWebhookHandler_DuplicateIP(t *testing.T) {
	if os.Getenv("INTEGRATION_TESTS") != "true" {
		t.Skip("Skipping integration tests")
	}

	// Setup similar to above but test duplicate IP handling
	gitlabURL := os.Getenv("GITLAB_URL")
	gitlabToken := os.Getenv("GITLAB_TOKEN")
	gitlabProjectID := os.Getenv("GITLAB_PROJECT_ID")

	require.NotEmpty(t, gitlabURL)
	require.NotEmpty(t, gitlabToken)
	require.NotEmpty(t, gitlabProjectID)

	// Create temp YAML with pre-existing IP
	tempDir, err := os.MkdirTemp("", "webhook-soar-dup-test-*")
	require.NoError(t, err)
	defer os.RemoveAll(tempDir)

	yamlPath := filepath.Join(tempDir, "test-objects.yaml")
	existingIP := "10.1.1.50"
	yamlContent := fmt.Sprintf(`
addresses:
  - name: pre-existing
    ip_netmask: %s/32
    description: "Pre-existing IP"
`, existingIP)

	err = os.WriteFile(yamlPath, []byte(yamlContent), 0644)
	require.NoError(t, err)

	// Setup components
	cfg := &config.Config{
		GitLabURL:       gitlabURL,
		GitLabToken:     gitlabToken,
		GitLabProjectID: gitlabProjectID,
		GitLabBranch:    "main",
		YAMLFilePath:    yamlPath,
		ObjectPath:      "addresses",
		ServerPort:      "8080",
	}

	repo, err := repository.NewGitLabRepository(
		cfg.GitLabURL,
		cfg.GitLabToken,
		cfg.GitLabProjectID,
		cfg.GitLabBranch,
	)
	require.NoError(t, err)

	yamlProc := service.NewYAMLProcessor(cfg.YAMLFilePath, cfg.ObjectPath)
	processor := service.NewProcessor(repo, yamlProc)
	webhookHandler := handler.NewWebhookHandler(processor)

	// Try to add the existing IP
	reqBody := map[string]interface{}{
		"ticket_id": "DUP-TEST-001",
		"attacker": map[string]interface{}{
			"type":  "ip_v4",
			"value": existingIP,
		},
		"reason": "Test duplicate handling",
	}

	body, _ := json.Marshal(reqBody)
	req := httptest.NewRequest("POST", "/webhook", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()
	req = req.WithContext(ctx)

	webhookHandler.HandleWebhook(w, req)

	// Should succeed but with MR ID 0 (no MR created for duplicate)
	assert.Equal(t, 200, w.Code)

	var resp handler.WebhookResponse
	err = json.Unmarshal(w.Body.Bytes(), &resp)
	require.NoError(t, err)

	assert.True(t, resp.Success)
	assert.Equal(t, 0, resp.MergeRequest, "Merge request ID should be 0 for duplicate IP")
	t.Logf("Correctly handled duplicate IP %s", existingIP)
}

func TestWebhookHandler_ErrorHandling(t *testing.T) {
	if os.Getenv("INTEGRATION_TESTS") != "true" {
		t.Skip("Skipping integration tests")
	}

	// Test error cases with minimal setup
	cfg := &config.Config{
		GitLabURL:       "https://invalid-url.example.com",
		GitLabToken:     "invalid-token",
		GitLabProjectID: "invalid-project",
		GitLabBranch:    "main",
		YAMLFilePath:    "/nonexistent/path.yaml",
		ObjectPath:      "addresses",
		ServerPort:      "8080",
	}

	repo, err := repository.NewGitLabRepository(
		cfg.GitLabURL,
		cfg.GitLabToken,
		cfg.GitLabProjectID,
		cfg.GitLabBranch,
	)
	require.NoError(t, err)

	yamlProc := service.NewYAMLProcessor(cfg.YAMLFilePath, cfg.ObjectPath)
	processor := service.NewProcessor(repo, yamlProc)
	webhookHandler := handler.NewWebhookHandler(processor)

	// Test with valid request but invalid backend
	reqBody := map[string]interface{}{
		"ticket_id": "ERROR-TEST-001",
		"attacker": map[string]interface{}{
			"type":  "ip_v4",
			"value": "10.2.2.100",
		},
		"reason": "Test error handling",
	}

	body, _ := json.Marshal(reqBody)
	req := httptest.NewRequest("POST", "/webhook", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	req = req.WithContext(ctx)

	webhookHandler.HandleWebhook(w, req)

	// Should return error
	assert.Equal(t, 500, w.Code)

	var resp handler.WebhookResponse
	err = json.Unmarshal(w.Body.Bytes(), &resp)
	require.NoError(t, err)

	assert.False(t, resp.Success)
	assert.Contains(t, resp.Message, "processing failed", "Error message should indicate processing failure")
	t.Logf("Correctly handled error: %s", resp.Message)
}

func TestProcessor_BranchNameGeneration(t *testing.T) {
	processor := &service.Processor{}

	// Test ticket ID sanitization
	tests := []struct {
		input    string
		expected string
	}{
		{"TICKET-123", "TICKET-123"},
		{"TICKET/123", "TICKET-123"},
		{"TICKET:123", "TICKET-123"},
		{"TICKET 123", "TICKET-123"},
		{"VERY-LONG-TICKET-ID-THAT-EXCEEDS-FIFTY-CHARACTERS-LIMIT", "VERY-LONG-TICKET-ID-THAT-EXCEEDS-FIFTY-CHARACTERS-LI"},
	}

	for _, tt := range tests {
		t.Run(tt.input, func(t *testing.T) {
			branchName := processor.GenerateBranchName(tt.input)
			assert.True(t, strings.HasPrefix(branchName, "soar-block-"), "Branch should start with 'soar-block-'")
			assert.True(t, strings.Contains(branchName, tt.expected), "Branch should contain sanitized ticket ID")
			assert.True(t, len(branchName) > len(tt.expected), "Branch should have timestamp appended")
		})
	}
}