package main

import (
	"log/slog"
	"os"

	"firewall-gitops/webhook-soar/internal/config"
)

func main() {
	// Setup structured logging
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	slog.SetDefault(logger)

	// Load configuration
	cfg, err := config.Load()
	if err != nil {
		slog.Error("failed to load config", "error", err)
		os.Exit(1)
	}

	slog.Info("webhook service starting",
		"gitlab_url", cfg.GitLabURL,
		"project_id", cfg.GitLabProjectID,
		"branch", cfg.GitLabBranch,
		"port", cfg.ServerPort)

	// TODO: Initialize HTTP server (Phase 04)
}
