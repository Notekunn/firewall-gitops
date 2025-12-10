package config

import (
	"fmt"
	"os"
	"strings"
)

type Config struct {
	GitLabURL        string
	GitLabToken      string
	GitLabProjectID  string
	GitLabBranch     string
	YAMLFilePath     string
	ObjectPath       string
	ServerPort       string
	WebhookAPIKey    string
	GitSkipTLSVerify bool
	GitUserName      string
	GitUserEmail     string
}

func Load() (*Config, error) {
	cfg := &Config{
		GitLabURL:        getEnv("GITLAB_URL", "https://gitlab.com"),
		GitLabToken:      os.Getenv("GITLAB_TOKEN"),
		GitLabProjectID:  os.Getenv("GITLAB_PROJECT_ID"),
		GitLabBranch:     getEnv("GITLAB_BRANCH", "main"),
		YAMLFilePath:     os.Getenv("YAML_FILE_PATH"),
		ObjectPath:       getEnv("OBJECT_PATH", "ip_lists.global.blocklist"),
		ServerPort:       getEnv("SERVER_PORT", "8080"),
		WebhookAPIKey:    os.Getenv("WEBHOOK_API_KEY"),
		GitSkipTLSVerify: getEnvBool("GIT_SKIP_TLS_VERIFY", false),
		GitUserName:      getEnv("GIT_USER_NAME", "SOAR Webhook"),
		GitUserEmail:     getEnv("GIT_USER_EMAIL", "soar-webhook@localhost"),
	}

	if err := cfg.Validate(); err != nil {
		return nil, fmt.Errorf("config validation failed: %w", err)
	}

	return cfg, nil
}

func (c *Config) Validate() error {
	if c.GitLabToken == "" {
		return fmt.Errorf("missing required env var: GITLAB_TOKEN")
	}
	if c.GitLabProjectID == "" {
		return fmt.Errorf("missing required env var: GITLAB_PROJECT_ID")
	}
	if c.YAMLFilePath == "" {
		return fmt.Errorf("missing required env var: YAML_FILE_PATH")
	}
	return nil
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func getEnvBool(key string, fallback bool) bool {
	v := strings.ToLower(os.Getenv(key))
	if v == "" {
		return fallback
	}
	return v == "true" || v == "1" || v == "yes"
}
