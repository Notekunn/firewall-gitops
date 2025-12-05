package config

import (
	"os"
	"testing"
)

func TestLoad(t *testing.T) {
	t.Run("success with all env vars set", func(t *testing.T) {
		// Store and set env vars
		envVars := map[string]string{
			"GITLAB_URL":        "https://gitlab.example.com",
			"GITLAB_TOKEN":      "token123",
			"GITLAB_PROJECT_ID": "42",
			"REPO_CLONE_URL":    "https://example.com/repo.git",
			"TARGET_CLUSTER":    "test-cluster",
			"WEBHOOK_SECRET":    "secret123",
			"SERVER_PORT":       "9000",
		}

		// Store original values
		original := make(map[string]string)
		for k, v := range envVars {
			original[k] = os.Getenv(k)
			os.Setenv(k, v)
		}

		// Restore after test
		defer func() {
			for k, v := range original {
				if v != "" {
					os.Setenv(k, v)
				} else {
					os.Unsetenv(k)
				}
			}
		}()

		cfg, err := Load()
		if err != nil {
			t.Fatalf("Load() returned error: %v", err)
		}

		if cfg.GitLabURL != "https://gitlab.example.com" {
			t.Errorf("Expected GitLabURL 'https://gitlab.example.com', got '%s'", cfg.GitLabURL)
		}
		if cfg.GitLabToken != "token123" {
			t.Errorf("Expected GitLabToken 'token123', got '%s'", cfg.GitLabToken)
		}
		if cfg.GitLabProjectID != "42" {
			t.Errorf("Expected GitLabProjectID '42', got '%s'", cfg.GitLabProjectID)
		}
		if cfg.RepoCloneURL != "https://example.com/repo.git" {
			t.Errorf("Expected RepoCloneURL 'https://example.com/repo.git', got '%s'", cfg.RepoCloneURL)
		}
		if cfg.TargetCluster != "test-cluster" {
			t.Errorf("Expected TargetCluster 'test-cluster', got '%s'", cfg.TargetCluster)
		}
		if cfg.WebhookSecret != "secret123" {
			t.Errorf("Expected WebhookSecret 'secret123', got '%s'", cfg.WebhookSecret)
		}
		if cfg.ServerPort != "9000" {
			t.Errorf("Expected ServerPort '9000', got '%s'", cfg.ServerPort)
		}
	})

	t.Run("success with default values", func(t *testing.T) {
		// Store and set env vars
		envVars := map[string]string{
			"GITLAB_URL":        "https://gitlab.example.com",
			"GITLAB_TOKEN":      "token123",
			"GITLAB_PROJECT_ID": "42",
			"REPO_CLONE_URL":    "https://example.com/repo.git",
			"WEBHOOK_SECRET":    "secret123",
			// TARGET_CLUSTER and SERVER_PORT not set to test defaults
		}

		// Store original values
		original := make(map[string]string)
		for k, v := range envVars {
			original[k] = os.Getenv(k)
			os.Setenv(k, v)
		}

		// Clear defaults to ensure they're not set
		os.Unsetenv("TARGET_CLUSTER")
		os.Unsetenv("SERVER_PORT")

		// Restore after test
		defer func() {
			for k, v := range original {
				if v != "" {
					os.Setenv(k, v)
				} else {
					os.Unsetenv(k)
				}
			}
		}()

		cfg, err := Load()
		if err != nil {
			t.Fatalf("Load() returned error: %v", err)
		}

		if cfg.TargetCluster != "f5-example" {
			t.Errorf("Expected default TargetCluster 'f5-example', got '%s'", cfg.TargetCluster)
		}
		if cfg.ServerPort != "8080" {
			t.Errorf("Expected default ServerPort '8080', got '%s'", cfg.ServerPort)
		}
	})

	t.Run("failure when required env var missing", func(t *testing.T) {
		// Store and set env vars (missing GITLAB_PROJECT_ID)
		envVars := map[string]string{
			"GITLAB_URL":     "https://gitlab.example.com",
			"GITLAB_TOKEN":   "token123",
			"REPO_CLONE_URL": "https://example.com/repo.git",
			"WEBHOOK_SECRET": "secret123",
		}

		// Store original values and ensure GITLAB_PROJECT_ID is not set
		original := make(map[string]string)
		for k, v := range envVars {
			original[k] = os.Getenv(k)
			os.Setenv(k, v)
		}
		original["GITLAB_PROJECT_ID"] = os.Getenv("GITLAB_PROJECT_ID")
		os.Unsetenv("GITLAB_PROJECT_ID")

		// Restore after test
		defer func() {
			for k, v := range original {
				if v != "" {
					os.Setenv(k, v)
				} else {
					os.Unsetenv(k)
				}
			}
		}()

		_, err := Load()
		if err == nil {
			t.Error("Expected error when GITLAB_PROJECT_ID is missing")
		}
		expectedError := "missing required env var: GITLAB_PROJECT_ID"
		if err.Error() != expectedError {
			t.Errorf("Expected error '%s', got '%s'", expectedError, err.Error())
		}
	})

	t.Run("failure when multiple required env vars missing", func(t *testing.T) {
		// Store original values
		original := make(map[string]string)
		requiredVars := []string{
			"GITLAB_URL", "GITLAB_TOKEN", "GITLAB_PROJECT_ID",
			"REPO_CLONE_URL", "WEBHOOK_SECRET",
		}
		for _, v := range requiredVars {
			original[v] = os.Getenv(v)
			os.Unsetenv(v)
		}

		// Set only some vars
		os.Setenv("GITLAB_TOKEN", "token123")
		os.Setenv("REPO_CLONE_URL", "https://example.com/repo.git")

		// Restore after test
		defer func() {
			for k, v := range original {
				if v != "" {
					os.Setenv(k, v)
				} else {
					os.Unsetenv(k)
				}
			}
		}()

		_, err := Load()
		if err == nil {
			t.Error("Expected error when required env vars are missing")
		}
		// Should return error for one of the missing required vars
		expectedErrors := []string{
			"missing required env var: GITLAB_URL",
			"missing required env var: GITLAB_PROJECT_ID",
			"missing required env var: WEBHOOK_SECRET",
		}
		found := false
		for _, expectedError := range expectedErrors {
			if err.Error() == expectedError {
				found = true
				break
			}
		}
		if !found {
			t.Errorf("Expected one of '%v', got '%s'", expectedErrors, err.Error())
		}
	})
}

func TestValidate(t *testing.T) {
	t.Run("valid config passes validation", func(t *testing.T) {
		cfg := &Config{
			GitLabURL:       "https://gitlab.example.com",
			GitLabToken:     "token123",
			GitLabProjectID: "42",
			RepoCloneURL:    "https://example.com/repo.git",
			TargetCluster:   "test-cluster",
			WebhookSecret:   "secret123",
			ServerPort:      "8080",
		}

		err := cfg.Validate()
		if err != nil {
			t.Errorf("Valid config should not return error: %v", err)
		}
	})

	t.Run("config with missing GitLabURL fails", func(t *testing.T) {
		cfg := &Config{
			GitLabURL:       "",
			GitLabToken:     "token123",
			GitLabProjectID: "42",
			RepoCloneURL:    "https://example.com/repo.git",
			WebhookSecret:   "secret123",
		}

		err := cfg.Validate()
		if err == nil {
			t.Error("Expected error when GitLabURL is empty")
		}
		expectedError := "missing required env var: GITLAB_URL"
		if err.Error() != expectedError {
			t.Errorf("Expected error '%s', got '%s'", expectedError, err.Error())
		}
	})

	t.Run("config with missing GitLabToken fails", func(t *testing.T) {
		cfg := &Config{
			GitLabURL:       "https://gitlab.example.com",
			GitLabToken:     "",
			GitLabProjectID: "42",
			RepoCloneURL:    "https://example.com/repo.git",
			WebhookSecret:   "secret123",
		}

		err := cfg.Validate()
		if err == nil {
			t.Error("Expected error when GitLabToken is empty")
		}
		expectedError := "missing required env var: GITLAB_TOKEN"
		if err.Error() != expectedError {
			t.Errorf("Expected error '%s', got '%s'", expectedError, err.Error())
		}
	})

	t.Run("config with missing GitLabProjectID fails", func(t *testing.T) {
		cfg := &Config{
			GitLabURL:       "https://gitlab.example.com",
			GitLabToken:     "token123",
			GitLabProjectID: "",
			RepoCloneURL:    "https://example.com/repo.git",
			WebhookSecret:   "secret123",
		}

		err := cfg.Validate()
		if err == nil {
			t.Error("Expected error when GitLabProjectID is empty")
		}
		expectedError := "missing required env var: GITLAB_PROJECT_ID"
		if err.Error() != expectedError {
			t.Errorf("Expected error '%s', got '%s'", expectedError, err.Error())
		}
	})

	t.Run("config with missing RepoCloneURL fails", func(t *testing.T) {
		cfg := &Config{
			GitLabURL:       "https://gitlab.example.com",
			GitLabToken:     "token123",
			GitLabProjectID: "42",
			RepoCloneURL:    "",
			WebhookSecret:   "secret123",
		}

		err := cfg.Validate()
		if err == nil {
			t.Error("Expected error when RepoCloneURL is empty")
		}
		expectedError := "missing required env var: REPO_CLONE_URL"
		if err.Error() != expectedError {
			t.Errorf("Expected error '%s', got '%s'", expectedError, err.Error())
		}
	})

	t.Run("config with missing WebhookSecret fails", func(t *testing.T) {
		cfg := &Config{
			GitLabURL:       "https://gitlab.example.com",
			GitLabToken:     "token123",
			GitLabProjectID: "42",
			RepoCloneURL:    "https://example.com/repo.git",
			WebhookSecret:   "",
		}

		err := cfg.Validate()
		if err == nil {
			t.Error("Expected error when WebhookSecret is empty")
		}
		expectedError := "missing required env var: WEBHOOK_SECRET"
		if err.Error() != expectedError {
			t.Errorf("Expected error '%s', got '%s'", expectedError, err.Error())
		}
	})
}

func TestGetEnv(t *testing.T) {
	t.Run("returns env var value when set", func(t *testing.T) {
		originalValue := os.Getenv("TEST_GET_ENV_VAR")
		os.Setenv("TEST_GET_ENV_VAR", "test-value")
		defer func() {
			if originalValue != "" {
				os.Setenv("TEST_GET_ENV_VAR", originalValue)
			} else {
				os.Unsetenv("TEST_GET_ENV_VAR")
			}
		}()

		result := getEnv("TEST_GET_ENV_VAR", "fallback")
		if result != "test-value" {
			t.Errorf("Expected 'test-value', got '%s'", result)
		}
	})

	t.Run("returns fallback when env var not set", func(t *testing.T) {
		originalValue := os.Getenv("TEST_GET_ENV_VAR_2")
		os.Unsetenv("TEST_GET_ENV_VAR_2")
		defer func() {
			if originalValue != "" {
				os.Setenv("TEST_GET_ENV_VAR_2", originalValue)
			}
		}()

		result := getEnv("TEST_GET_ENV_VAR_2", "fallback-value")
		if result != "fallback-value" {
			t.Errorf("Expected 'fallback-value', got '%s'", result)
		}
	})

	t.Run("returns fallback when env var is empty", func(t *testing.T) {
		originalValue := os.Getenv("TEST_GET_ENV_VAR_3")
		os.Setenv("TEST_GET_ENV_VAR_3", "")
		defer func() {
			if originalValue != "" {
				os.Setenv("TEST_GET_ENV_VAR_3", originalValue)
			} else {
				os.Unsetenv("TEST_GET_ENV_VAR_3")
			}
		}()

		result := getEnv("TEST_GET_ENV_VAR_3", "fallback-value")
		if result != "fallback-value" {
			t.Errorf("Expected 'fallback-value', got '%s'", result)
		}
	})
}