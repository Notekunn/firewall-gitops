package config

import (
	"fmt"
	"os"
)

type Config struct {
	GitLabURL       string
	GitLabToken     string
	GitLabProjectID string
	RepoCloneURL    string
	TargetCluster   string
	WebhookSecret   string
	ServerPort      string
}

func Load() (*Config, error) {
	cfg := &Config{
		GitLabURL:       getEnv("GITLAB_URL", ""),
		GitLabToken:     getEnv("GITLAB_TOKEN", ""),
		GitLabProjectID: getEnv("GITLAB_PROJECT_ID", ""),
		RepoCloneURL:    getEnv("REPO_CLONE_URL", ""),
		TargetCluster:   getEnv("TARGET_CLUSTER", "f5-example"),
		WebhookSecret:   getEnv("WEBHOOK_SECRET", ""),
		ServerPort:      getEnv("SERVER_PORT", "8080"),
	}

	if err := cfg.Validate(); err != nil {
		return nil, err
	}
	return cfg, nil
}

func (c *Config) Validate() error {
	required := map[string]string{
		"GITLAB_URL":        c.GitLabURL,
		"GITLAB_TOKEN":      c.GitLabToken,
		"GITLAB_PROJECT_ID": c.GitLabProjectID,
		"REPO_CLONE_URL":    c.RepoCloneURL,
		"WEBHOOK_SECRET":    c.WebhookSecret,
	}
	for name, val := range required {
		if val == "" {
			return fmt.Errorf("missing required env var: %s", name)
		}
	}
	return nil
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}