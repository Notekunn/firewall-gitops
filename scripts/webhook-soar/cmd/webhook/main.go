package main

import (
	"context"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"firewall-gitops/webhook-soar/internal/config"
	"firewall-gitops/webhook-soar/internal/handler"
	"firewall-gitops/webhook-soar/internal/repository"
	"firewall-gitops/webhook-soar/internal/service"
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	slog.SetDefault(logger)

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
	repo, err := repository.NewGitLabRepository(
		cfg.GitLabURL,
		cfg.GitLabToken,
		cfg.GitLabProjectID,
		cfg.GitLabBranch,
		cfg.GitSkipTLSVerify,
	)
	if err != nil {
		slog.Error("failed to initialize gitlab repository", "error", err)
		os.Exit(1)
	}

	// Initialize YAML processor
	yamlProc := service.NewYAMLProcessor(cfg.YAMLFilePath, cfg.ObjectPath)

	// Initialize processor that orchestrates the workflow
	processor := service.NewProcessor(repo, yamlProc)

	// Initialize webhook handler
	webhookHandler := handler.NewWebhookHandler(processor, cfg.WebhookAPIKey)

	// Setup HTTP routes
	mux := http.NewServeMux()
	mux.HandleFunc("/webhook", webhookHandler.HandleWebhook)
	mux.HandleFunc("/health", webhookHandler.HandleHealth)

	// Add root endpoint for basic info
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/" {
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{
			"service": "SOAR Webhook Service",
			"version": "1.0.0",
			"status": "running",
			"endpoints": {
				"webhook": "/webhook",
				"health": "/health"
			}
		}`))
	})

	// Create HTTP server with timeouts
	server := &http.Server{
		Addr:         ":" + cfg.ServerPort,
		Handler:      mux,
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 40 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	// Channel to receive errors from server
	serverErrors := make(chan error, 1)

	// Start server in goroutine
	go func() {
		slog.Info("http server listening", "port", cfg.ServerPort)
		serverErrors <- server.ListenAndServe()
	}()

	// Wait for interrupt or server error
	select {
	case err := <-serverErrors:
		if err != nil && err != http.ErrServerClosed {
			slog.Error("server error", "error", err)
			os.Exit(1)
		}
	case sig := <-signalChannel():
		slog.Info("received signal, shutting down gracefully", "signal", sig)

		// Create shutdown context with timeout
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()

		// Shutdown server
		if err := server.Shutdown(ctx); err != nil {
			slog.Error("shutdown error", "error", err)
			os.Exit(1)
		}

		slog.Info("server stopped gracefully")
	}
}

// signalChannel creates a channel for OS signals
func signalChannel() chan os.Signal {
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)
	return sigChan
}
