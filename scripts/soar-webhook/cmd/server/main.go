package main

import (
	"log/slog"
	"os"

	"github.com/notekunn/firewall-gitops/scripts/soar-webhook/internal/config"
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	slog.SetDefault(logger)

	cfg, err := config.Load()
	if err != nil {
		slog.Error("failed to load config", "error", err)
		os.Exit(1)
	}

	slog.Info("starting server", "port", cfg.ServerPort)
	// TODO: Initialize handlers and start server (Phase 04)
}