package config

import (
	"os"
	"testing"
)

func TestLoad(t *testing.T) {
	tests := []struct {
		name        string
		envVars     map[string]string
		wantErr     bool
		errContains string
	}{
		{
			name: "success with all env vars",
			envVars: map[string]string{
				"GITLAB_TOKEN":      "test-token",
				"GITLAB_PROJECT_ID": "123",
				"YAML_FILE_PATH":    "clusters/production/objects.yaml",
				"GITLAB_URL":        "https://gitlab.example.com",
				"GITLAB_BRANCH":     "develop",
				"OBJECT_PATH":       "ip_lists.custom.blocklist",
				"SERVER_PORT":       "9090",
			},
			wantErr: false,
		},
		{
			name: "success with defaults",
			envVars: map[string]string{
				"GITLAB_TOKEN":      "test-token",
				"GITLAB_PROJECT_ID": "123",
				"YAML_FILE_PATH":    "clusters/test/objects.yaml",
			},
			wantErr: false,
		},
		{
			name: "with api key and skip tls",
			envVars: map[string]string{
				"GITLAB_TOKEN":        "test-token",
				"GITLAB_PROJECT_ID":   "123",
				"YAML_FILE_PATH":      "clusters/test/objects.yaml",
				"WEBHOOK_API_KEY":     "secret-key",
				"GIT_SKIP_TLS_VERIFY": "true",
			},
			wantErr: false,
		},
		{
			name: "missing GITLAB_TOKEN",
			envVars: map[string]string{
				"GITLAB_PROJECT_ID": "123",
				"YAML_FILE_PATH":    "clusters/test/objects.yaml",
			},
			wantErr:     true,
			errContains: "GITLAB_TOKEN",
		},
		{
			name: "missing GITLAB_PROJECT_ID",
			envVars: map[string]string{
				"GITLAB_TOKEN":   "test-token",
				"YAML_FILE_PATH": "clusters/test/objects.yaml",
			},
			wantErr:     true,
			errContains: "GITLAB_PROJECT_ID",
		},
		{
			name: "missing YAML_FILE_PATH",
			envVars: map[string]string{
				"GITLAB_TOKEN":      "test-token",
				"GITLAB_PROJECT_ID": "123",
			},
			wantErr:     true,
			errContains: "YAML_FILE_PATH",
		},
		{
			name: "missing all required vars",
			envVars: map[string]string{
				"SERVER_PORT": "8080",
			},
			wantErr:     true,
			errContains: "GITLAB_TOKEN",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Clear env vars before each test
			for _, key := range []string{
				"GITLAB_URL", "GITLAB_TOKEN", "GITLAB_PROJECT_ID",
				"GITLAB_BRANCH", "YAML_FILE_PATH", "OBJECT_PATH", "SERVER_PORT",
				"WEBHOOK_API_KEY", "GIT_SKIP_TLS_VERIFY",
			} {
				os.Unsetenv(key)
			}

			// Set test env vars
			for k, v := range tt.envVars {
				os.Setenv(k, v)
			}

			// Restore env vars after test
			defer func() {
				for k := range tt.envVars {
					os.Unsetenv(k)
				}
			}()

			cfg, err := Load()

			if tt.wantErr {
				if err == nil {
					t.Errorf("Load() expected error, got nil")
					return
				}
				if tt.errContains != "" && err.Error() != tt.errContains && err.Error()[len(err.Error())-len(tt.errContains):] != tt.errContains {
					// Check if error message contains expected string
					if len(err.Error()) < len(tt.errContains) || err.Error()[len(err.Error())-len(tt.errContains):] != tt.errContains {
						t.Errorf("Load() error = %v, expected to contain %v", err, tt.errContains)
					}
				}
				return
			}

			if err != nil {
				t.Errorf("Load() unexpected error = %v", err)
				return
			}

			// Verify config values
			if cfg.GitLabToken != tt.envVars["GITLAB_TOKEN"] {
				t.Errorf("GitLabToken = %v, want %v", cfg.GitLabToken, tt.envVars["GITLAB_TOKEN"])
			}
			if cfg.GitLabProjectID != tt.envVars["GITLAB_PROJECT_ID"] {
				t.Errorf("GitLabProjectID = %v, want %v", cfg.GitLabProjectID, tt.envVars["GITLAB_PROJECT_ID"])
			}
			if cfg.YAMLFilePath != tt.envVars["YAML_FILE_PATH"] {
				t.Errorf("YAMLFilePath = %v, want %v", cfg.YAMLFilePath, tt.envVars["YAML_FILE_PATH"])
			}

			// Check defaults
			if tt.envVars["GITLAB_URL"] == "" && cfg.GitLabURL != "https://gitlab.com" {
				t.Errorf("GitLabURL = %v, want default https://gitlab.com", cfg.GitLabURL)
			}
			if tt.envVars["GITLAB_BRANCH"] == "" && cfg.GitLabBranch != "main" {
				t.Errorf("GitLabBranch = %v, want default main", cfg.GitLabBranch)
			}
			if tt.envVars["OBJECT_PATH"] == "" && cfg.ObjectPath != "ip_lists.global.blocklist" {
				t.Errorf("ObjectPath = %v, want default ip_lists.global.blocklist", cfg.ObjectPath)
			}
			if tt.envVars["SERVER_PORT"] == "" && cfg.ServerPort != "8080" {
				t.Errorf("ServerPort = %v, want default 8080", cfg.ServerPort)
			}
			// Check new fields
			if cfg.WebhookAPIKey != tt.envVars["WEBHOOK_API_KEY"] {
				t.Errorf("WebhookAPIKey = %v, want %v", cfg.WebhookAPIKey, tt.envVars["WEBHOOK_API_KEY"])
			}
			wantSkipTLS := tt.envVars["GIT_SKIP_TLS_VERIFY"] == "true" || tt.envVars["GIT_SKIP_TLS_VERIFY"] == "1" || tt.envVars["GIT_SKIP_TLS_VERIFY"] == "yes"
			if cfg.GitSkipTLSVerify != wantSkipTLS {
				t.Errorf("GitSkipTLSVerify = %v, want %v", cfg.GitSkipTLSVerify, wantSkipTLS)
			}
		})
	}
}

func TestConfigValidate(t *testing.T) {
	tests := []struct {
		name        string
		config      Config
		wantErr     bool
		errContains string
	}{
		{
			name: "valid config",
			config: Config{
				GitLabToken:     "test-token",
				GitLabProjectID: "123",
				YAMLFilePath:    "test.yaml",
			},
			wantErr: false,
		},
		{
			name: "missing token",
			config: Config{
				GitLabProjectID: "123",
				YAMLFilePath:    "test.yaml",
			},
			wantErr:     true,
			errContains: "GITLAB_TOKEN",
		},
		{
			name: "missing project id",
			config: Config{
				GitLabToken:  "test-token",
				YAMLFilePath: "test.yaml",
			},
			wantErr:     true,
			errContains: "GITLAB_PROJECT_ID",
		},
		{
			name: "missing yaml path",
			config: Config{
				GitLabToken:     "test-token",
				GitLabProjectID: "123",
			},
			wantErr:     true,
			errContains: "YAML_FILE_PATH",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.config.Validate()
			if tt.wantErr {
				if err == nil {
					t.Errorf("Validate() expected error, got nil")
				}
				if tt.errContains != "" && err.Error() != tt.errContains && err.Error()[len(err.Error())-len(tt.errContains):] != tt.errContains {
					t.Errorf("Validate() error = %v, expected to contain %v", err, tt.errContains)
				}
			} else if err != nil {
				t.Errorf("Validate() unexpected error = %v", err)
			}
		})
	}
}
