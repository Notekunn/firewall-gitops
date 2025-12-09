package main

import (
	"log/slog"
	"os"

	"firewall-gitops/webhook-soar/internal/config"
	"firewall-gitops/webhook-soar/internal/repository"
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

	// Initialize GitLab repository
	_, err = repository.NewGitLabRepository(
		cfg.GitLabURL,
		cfg.GitLabToken,
		cfg.GitLabProjectID,
		cfg.GitLabBranch,
	)
	if err != nil {
		slog.Error("failed to initialize gitlab repository", "error", err)
		os.Exit(1)
	}

	slog.Info("gitlab repository initialized successfully",
		"project_id", cfg.GitLabProjectID,
		"base_branch", cfg.GitLabBranch)

	// TODO: Initialize HTTP server (Phase 04)
}
