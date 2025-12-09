package service

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"gopkg.in/yaml.v3"
)

func TestYAMLProcessor_AddIP(t *testing.T) {
	tests := []struct {
		name        string
		yamlContent string
		objectPath  string
		ip          string
		expectAdd   bool
		expectError bool
	}{
		{
			name: "add new IP to existing list",
			yamlContent: `ip_lists:
  global:
    blocklist:
      - "10.0.0.1/32"
`,
			objectPath: "ip_lists.global.blocklist",
			ip:         "10.0.0.2",
			expectAdd:  true,
		},
		{
			name: "prevent duplicate IP",
			yamlContent: `ip_lists:
  global:
    blocklist:
      - "10.0.0.1/32"
`,
			objectPath: "ip_lists.global.blocklist",
			ip:         "10.0.0.1",
			expectAdd:  false,
		},
		{
			name: "prevent duplicate IP with different CIDR",
			yamlContent: `ip_lists:
  global:
    blocklist:
      - "10.0.0.1/32"
`,
			objectPath: "ip_lists.global.blocklist",
			ip:         "10.0.0.1/32",
			expectAdd:  false,
		},
		{
			name: "add IP to empty list",
			yamlContent: `ip_lists:
  global:
    blocklist: []
`,
			objectPath: "ip_lists.global.blocklist",
			ip:         "10.0.0.1",
			expectAdd:  true,
		},
		{
			name: "invalid IP format",
			yamlContent: `ip_lists:
  global:
    blocklist: []
`,
			objectPath:  "ip_lists.global.blocklist",
			ip:          "invalid-ip",
			expectAdd:   false,
			expectError: true,
		},
		{
			name: "path not found",
			yamlContent: `ip_lists:
  global:
    allowlist: []
`,
			objectPath:  "ip_lists.global.blocklist",
			ip:          "10.0.0.1",
			expectAdd:   false,
			expectError: true,
		},
		{
			name: "target not a list",
			yamlContent: `ip_lists:
  global:
    blocklist: "not-a-list"
`,
			objectPath:  "ip_lists.global.blocklist",
			ip:          "10.0.0.1",
			expectAdd:   false,
			expectError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Create temp directory
			tempDir, err := os.MkdirTemp("", "yaml-test-*")
			assert.NoError(t, err)
			defer os.RemoveAll(tempDir)

			// Create YAML file
			yamlFile := filepath.Join(tempDir, "test.yaml")
			err = os.WriteFile(yamlFile, []byte(tt.yamlContent), 0644)
			assert.NoError(t, err)

			// Create processor
			processor := NewYAMLProcessor("test.yaml", tt.objectPath)

			// Add IP
			added, err := processor.AddIP(tempDir, tt.ip)

			if tt.expectError {
				assert.Error(t, err)
				return
			}
			assert.NoError(t, err)
			assert.Equal(t, tt.expectAdd, added)

			// Read result if IP was added
			if tt.expectAdd {
				content, err := os.ReadFile(yamlFile)
				assert.NoError(t, err)

				// Parse YAML to verify structure
				var root map[string]interface{}
				err = yaml.Unmarshal(content, &root)
				assert.NoError(t, err)

				// Navigate to the list
				parts := strings.Split(tt.objectPath, ".")
				current := root
				for i := 0; i < len(parts)-1; i++ {
					current = current[parts[i]].(map[string]interface{})
				}

				list := current[parts[len(parts)-1]].([]interface{})
				assert.Greater(t, len(list), 0)

				// Check if IP with /32 suffix is in list
				found := false
				expectedIP := tt.ip
				if !strings.Contains(expectedIP, "/") {
					expectedIP = expectedIP + "/32"
				}
				for _, item := range list {
					if item == expectedIP {
						found = true
						break
					}
				}
				assert.True(t, found, "IP %s not found in list", expectedIP)
			}
		})
	}
}

func TestYAMLProcessor_CommentPreservation(t *testing.T) {
	// YAML with comments
	yamlWithComments := `# IP Lists Configuration
ip_lists:
  global:
    # Block malicious IPs
    blocklist:
      - "10.0.0.1/32"  # First blocked IP
`

	tempDir, err := os.MkdirTemp("", "yaml-comment-test-*")
	assert.NoError(t, err)
	defer os.RemoveAll(tempDir)

	yamlFile := filepath.Join(tempDir, "test.yaml")
	err = os.WriteFile(yamlFile, []byte(yamlWithComments), 0644)
	assert.NoError(t, err)

	processor := NewYAMLProcessor("test.yaml", "ip_lists.global.blocklist")
	added, err := processor.AddIP(tempDir, "10.0.0.2")
	assert.NoError(t, err)
	assert.True(t, added)

	// Read result
	content, err := os.ReadFile(yamlFile)
	assert.NoError(t, err)

	contentStr := string(content)
	// Check comments are preserved
	assert.Contains(t, contentStr, "# IP Lists Configuration")
	assert.Contains(t, contentStr, "# Block malicious IPs")
	assert.Contains(t, contentStr, "# First blocked IP")
	// Check new IP is added
	assert.Contains(t, contentStr, `"10.0.0.2/32"`)
}

func TestYAMLProcessor_Indentation(t *testing.T) {
	yamlContent := `ip_lists:
  global:
    blocklist:
      - "10.0.0.1/32"
`

	tempDir, err := os.MkdirTemp("", "yaml-indent-test-*")
	assert.NoError(t, err)
	defer os.RemoveAll(tempDir)

	yamlFile := filepath.Join(tempDir, "test.yaml")
	err = os.WriteFile(yamlFile, []byte(yamlContent), 0644)
	assert.NoError(t, err)

	processor := NewYAMLProcessor("test.yaml", "ip_lists.global.blocklist")
	added, err := processor.AddIP(tempDir, "10.0.0.2")
	assert.NoError(t, err)
	assert.True(t, added)

	// Read result
	content, err := os.ReadFile(yamlFile)
	assert.NoError(t, err)

	lines := strings.Split(string(content), "\n")

	// Check indentation is 2 spaces
	for _, line := range lines {
		if strings.HasPrefix(line, " ") {
			// Count leading spaces
			trimmed := strings.TrimLeft(line, " ")
			spaces := len(line) - len(trimmed)
			assert.Equal(t, 0, spaces%2, "Indentation should be multiple of 2 spaces")
		}
	}
}

func TestValidateIP(t *testing.T) {
	tests := []struct {
		ip      string
		wantErr bool
	}{
		{"10.0.0.1", false},
		{"10.0.0.1/32", false},
		{"192.168.1.1", false},
		{"255.255.255.255", false},
		{"0.0.0.0", false},
		{"invalid-ip", true},
		{"256.256.256.256", true},
		{"", true},
		{"10.0.0", true},
	}

	for _, tt := range tests {
		t.Run(tt.ip, func(t *testing.T) {
			err := validateIP(tt.ip)
			if tt.wantErr {
				assert.Error(t, err)
			} else {
				assert.NoError(t, err)
			}
		})
	}
}

func TestNormalizeIP(t *testing.T) {
	tests := []struct {
		input  string
		output string
	}{
		{"10.0.0.1", "10.0.0.1"},
		{"10.0.0.1/32", "10.0.0.1"},
		{"192.168.1.1/24", "192.168.1.1"},
		{"0.0.0.0/0", "0.0.0.0"},
	}

	for _, tt := range tests {
		t.Run(tt.input, func(t *testing.T) {
			result := normalizeIP(tt.input)
			assert.Equal(t, tt.output, result)
		})
	}
}
