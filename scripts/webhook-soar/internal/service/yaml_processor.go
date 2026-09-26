package service

import (
	"fmt"
	"net"
	"os"
	"path/filepath"
	"strings"

	"gopkg.in/yaml.v3"
)

type YAMLProcessor struct {
	filePath   string // Relative path in repo
	objectPath string // Dot-separated path
}

func NewYAMLProcessor(filePath, objectPath string) *YAMLProcessor {
	return &YAMLProcessor{
		filePath:   filePath,
		objectPath: objectPath,
	}
}

// AddIP adds IP to blocklist if not exists
func (p *YAMLProcessor) AddIP(repoPath, ip string) (bool, error) {
	// Validate IP format
	if err := validateIP(ip); err != nil {
		return false, fmt.Errorf("invalid ip: %w", err)
	}

	fullPath := filepath.Join(repoPath, p.filePath)

	// Read YAML
	data, err := os.ReadFile(fullPath)
	if err != nil {
		return false, fmt.Errorf("failed to read yaml: %w", err)
	}

	var root yaml.Node
	if err := yaml.Unmarshal(data, &root); err != nil {
		return false, fmt.Errorf("failed to parse yaml: %w", err)
	}

	// Navigate to target list
	listNode, err := p.navigateToList(&root)
	if err != nil {
		return false, fmt.Errorf("failed to navigate path: %w", err)
	}

	// Check for duplicate
	if p.containsIP(listNode, ip) {
		return false, nil // Already exists, not an error
	}

	// Append IP
	p.appendIP(listNode, ip)

	// Marshal back to YAML with 2-space indentation
	output, err := p.marshalYAML(&root)
	if err != nil {
		return false, fmt.Errorf("failed to marshal yaml: %w", err)
	}

	// Write back
	if err := os.WriteFile(fullPath, output, 0644); err != nil {
		return false, fmt.Errorf("failed to write yaml: %w", err)
	}

	return true, nil
}

// navigateToList walks object path and returns list node
func (p *YAMLProcessor) navigateToList(root *yaml.Node) (*yaml.Node, error) {
	parts := strings.Split(p.objectPath, ".")
	current := root

	// Root is document node, get first content
	if current.Kind == yaml.DocumentNode && len(current.Content) > 0 {
		current = current.Content[0]
	}

	for _, part := range parts {
		found := false

		if current.Kind != yaml.MappingNode {
			return nil, fmt.Errorf("expected mapping at %s, got %v", part, current.Kind)
		}

		// Mapping nodes: [key1, val1, key2, val2, ...]
		for i := 0; i < len(current.Content); i += 2 {
			keyNode := current.Content[i]
			valNode := current.Content[i+1]

			if keyNode.Value == part {
				current = valNode
				found = true
				break
			}
		}

		if !found {
			return nil, fmt.Errorf("path not found: %s", part)
		}
	}

	if current.Kind != yaml.SequenceNode {
		return nil, fmt.Errorf("target is not a list")
	}

	return current, nil
}

// containsIP checks if IP exists in list
func (p *YAMLProcessor) containsIP(listNode *yaml.Node, ip string) bool {
	normalizedIP := normalizeIP(ip)

	for _, item := range listNode.Content {
		if item.Kind == yaml.ScalarNode {
			if normalizeIP(item.Value) == normalizedIP {
				return true
			}
		}
	}
	return false
}

// appendIP adds IP to list
func (p *YAMLProcessor) appendIP(listNode *yaml.Node, ip string) {
	// // Add /32 suffix if not present
	// ipWithCIDR := ip
	// if !strings.Contains(ip, "/") {
	// 	ipWithCIDR = ip + "/32"
	// }

	newNode := &yaml.Node{
		Kind:  yaml.ScalarNode,
		Value: ip,
		Style: yaml.DoubleQuotedStyle,
	}

	listNode.Content = append(listNode.Content, newNode)
}

// validateIP validates IP address format
func validateIP(ip string) error {
	// Strip CIDR suffix if present
	ipOnly := strings.Split(ip, "/")[0]

	if net.ParseIP(ipOnly) == nil {
		return fmt.Errorf("invalid ip address: %s", ip)
	}

	return nil
}

// normalizeIP strips CIDR for comparison
func normalizeIP(ip string) string {
	return strings.Split(ip, "/")[0]
}

// marshalYAML marshals YAML with custom settings
func (p *YAMLProcessor) marshalYAML(node *yaml.Node) ([]byte, error) {
	var buf strings.Builder
	enc := yaml.NewEncoder(&buf)
	enc.SetIndent(2) // Use 2-space indentation as per project standards

	if err := enc.Encode(node); err != nil {
		return nil, err
	}

	// Convert string buffer to bytes
	return []byte(buf.String()), nil
}
