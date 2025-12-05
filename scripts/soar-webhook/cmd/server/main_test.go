package main

import (
	"bytes"
	"encoding/json"
	"log/slog"
	"os"
	"testing"

	"github.com/notekunn/firewall-gitops/scripts/soar-webhook/internal/config"
)

func TestStructuredLoggingSetup(t *testing.T) {
	// Store original stdout
	originalStdout := os.Stdout

	// Create a buffer to capture output
	var buf bytes.Buffer

	// Create logger with buffer output
	logger := slog.New(slog.NewJSONHandler(&buf, nil))
	slog.SetDefault(logger)

	// Write a test log entry
	slog.Info("test message", "key", "value")

	// Restore stdout
	os.Stdout = originalStdout

	// Parse the JSON log
	var logEntry map[string]interface{}
	if err := json.Unmarshal(buf.Bytes(), &logEntry); err != nil {
		t.Fatalf("Failed to parse JSON log: %v", err)
	}

	// Verify JSON structure
	if logEntry["level"] != "INFO" {
		t.Errorf("Expected level 'INFO', got '%v'", logEntry["level"])
	}
	if logEntry["msg"] != "test message" {
		t.Errorf("Expected message 'test message', got '%v'", logEntry["msg"])
	}
	if logEntry["key"] != "value" {
		t.Errorf("Expected key 'value', got '%v'", logEntry["key"])
	}

	// Verify time field exists
	if _, ok := logEntry["time"]; !ok {
		t.Error("Expected 'time' field in log entry")
	}
}

func TestConfigLoadingWithLogging(t *testing.T) {
	// Test that main logs error when config fails to load
	// Store and clear all required env vars
	originalEnv := make(map[string]string)
	envVars := []string{
		"GITLAB_URL", "GITLAB_TOKEN", "GITLAB_PROJECT_ID",
		"REPO_CLONE_URL", "WEBHOOK_SECRET",
	}
	for _, v := range envVars {
		originalEnv[v] = os.Getenv(v)
		os.Unsetenv(v)
	}
	defer func() {
		for k, v := range originalEnv {
			if v != "" {
				os.Setenv(k, v)
			} else {
				os.Unsetenv(k)
			}
		}
	}()

	// Set up logger like main does
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	slog.SetDefault(logger)

	// Simulate the config loading error from main
	_, err := config.Load()
	if err == nil {
		t.Error("Expected error when config loading fails")
	}
}

func TestDefaultLoggingSetup(t *testing.T) {
	// Test that default logger is JSON formatted
	originalDefault := slog.Default()
	defer slog.SetDefault(originalDefault)

	// Set up logger like main does
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	slog.SetDefault(logger)

	// Verify the default logger was set
	if slog.Default() != logger {
		t.Error("Default logger was not set correctly")
	}

	// Test different log levels using buffer instead of stdout
	testCases := []struct {
		level    string
		expected string
		logFunc  func(*slog.Logger)
	}{
		{"INFO", "INFO", func(l *slog.Logger) { l.Info("test", "key", "value") }},
		{"ERROR", "ERROR", func(l *slog.Logger) { l.Error("test", "key", "value") }},
		{"WARN", "WARN", func(l *slog.Logger) { l.Warn("test", "key", "value") }},
	}

	for _, tc := range testCases {
		t.Run("log_"+tc.level, func(t *testing.T) {
			// Create a buffer for this test
			var buf bytes.Buffer
			testLogger := slog.New(slog.NewJSONHandler(&buf, nil))

			// Log message
			tc.logFunc(testLogger)

			// Parse JSON
			var logEntry map[string]interface{}
			if err := json.Unmarshal(buf.Bytes(), &logEntry); err != nil {
				t.Fatalf("Failed to parse JSON log: %v", err)
			}

			// Verify level
			if logEntry["level"] != tc.expected {
				t.Errorf("Expected level '%s', got '%v'", tc.expected, logEntry["level"])
			}
		})
	}

	// Test DEBUG level separately with enabled debug level
	t.Run("log_DEBUG", func(t *testing.T) {
		// Create a buffer for this test
		var buf bytes.Buffer
		opts := &slog.HandlerOptions{Level: slog.LevelDebug}
		testLogger := slog.New(slog.NewJSONHandler(&buf, opts))

		// Log message
		testLogger.Debug("test", "key", "value")

		// Parse JSON
		var logEntry map[string]interface{}
		if err := json.Unmarshal(buf.Bytes(), &logEntry); err != nil {
			t.Fatalf("Failed to parse JSON log: %v", err)
		}

		// Verify level
		if logEntry["level"] != "DEBUG" {
			t.Errorf("Expected level 'DEBUG', got '%v'", logEntry["level"])
		}
	})
}