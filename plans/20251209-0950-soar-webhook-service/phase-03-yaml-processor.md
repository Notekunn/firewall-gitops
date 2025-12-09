# Phase 03: YAML Parsing & IP Management

**Priority:** High
**Status:** Done (2025-12-09)
**Dependencies:** Phase 01

## Overview

Parse YAML files, navigate object paths, add IPs to blocklists without duplicates, preserve formatting and comments.

## Key Insights

- YAML structure varies per cluster (objects.yaml vs objects/*.yaml)
- Object path: `ip_lists.global.blocklist` means nested structure
- Must preserve YAML comments, formatting, order
- gopkg.in/yaml.v3 supports comment preservation
- Deduplication: check if IP already exists before adding

## Requirements

### Functional
- Read YAML file from repository
- Navigate nested object path (dot notation)
- Extract IP list from target path
- Check for duplicate IPs
- Append new IP if not exists
- Write YAML back preserving format
- Support both ip_netmask format and plain IP strings

### Non-Functional
- Preserve YAML comments
- Maintain indentation (2 spaces)
- Handle missing intermediate keys gracefully
- Validate IP format before adding

## Architecture

```
Service → YAMLProcessor.AddIP() → Parse → Navigate Path → Dedupe → Update → Write
```

**Object Path Example:**
```yaml
# Config: object_path = "ip_lists.global.blocklist"
ip_lists:
  global:
    blocklist:
      - "1.1.1.1/32"
      - "2.2.2.2/32"
```

## Related Code Files

**Create:**
- `internal/service/yaml_processor.go` - YAML operations
- `internal/service/yaml_processor_test.go` - Unit tests

**Modify:**
- `go.mod` - Add yaml.v3 dependency

## Implementation Steps

### 1. Add Dependencies
```bash
go get gopkg.in/yaml.v3@latest
```

### 2. Implement YAML Processor
**File:** `internal/service/yaml_processor.go`

```go
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

    // Marshal back to YAML
    output, err := yaml.Marshal(&root)
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
    // Add /32 suffix if not present
    ipWithCIDR := ip
    if !strings.Contains(ip, "/") {
        ipWithCIDR = ip + "/32"
    }

    newNode := &yaml.Node{
        Kind:  yaml.ScalarNode,
        Value: ipWithCIDR,
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
```

### 3. Write Tests
**File:** `internal/service/yaml_processor_test.go`

Test scenarios:
- Add new IP to empty list
- Add IP to existing list
- Prevent duplicate IP (with/without CIDR)
- Navigate nested object paths
- Handle missing paths (error)
- Validate IP format
- Preserve YAML comments and formatting

**Test YAML fixture:**
```yaml
# IP Lists Configuration
ip_lists:
  global:
    blocklist:
      - "10.0.0.1/32"  # Existing blocked IP
```

### 4. Integration Test
Create end-to-end test:
1. Create temp YAML file
2. Add multiple IPs
3. Verify deduplication
4. Check YAML structure preserved

## Completed Tasks

- [x] Add gopkg.in/yaml.v3 dependency
- [x] Implement YAMLProcessor struct
- [x] Implement navigateToList() for path walking
- [x] Implement containsIP() for deduplication
- [x] Implement appendIP() with CIDR normalization
- [x] Implement validateIP() for input validation
- [x] Implement AddIP() orchestration method
- [x] Write unit tests for each method
- [x] Write integration test with real YAML
- [x] Test comment preservation
- [x] Verify 2-space indentation maintained

## Success Criteria

- Parse YAML with nested structures
- Navigate dot-notation paths correctly
- Deduplicate IPs (ignore CIDR differences)
- Add IPs with /32 suffix
- Preserve YAML comments and formatting
- All tests pass

## Risk Assessment

**Medium risk** - YAML parsing, path navigation, format preservation.

**Mitigations:**
- Use yaml.v3 Node API (preserves comments)
- Extensive unit tests with various YAML structures
- Validate all inputs before processing
- Handle missing paths gracefully

## Security Considerations

- Validate IP format before adding (prevent injection)
- Limit IP list size (DoS prevention)
- Check file permissions before write
- Sanitize object path (prevent path traversal)

## Next Steps

After phase 03:
- Phase 04: HTTP webhook handler
- Integrate YAMLProcessor with GitLab repository
- Create service layer orchestrating end-to-end flow
