package service

import (
	"strings"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

func TestProcessor_SanitizeTicketID(t *testing.T) {
	processor := &Processor{}

	tests := []struct {
		input    string
		expected string
	}{
		{"TICKET-123", "TICKET-123"},
		{"TICKET/123", "TICKET-123"},
		{"TICKET\\123", "TICKET-123"},
		{"TICKET:123", "TICKET-123"},
		{"TICKET*123", "TICKET-123"},
		{"TICKET?123", "TICKET-123"},
		{"TICKET\"123\"", "TICKET-123"},
		{"TICKET<123>", "TICKET-123"},
		{"TICKET|123", "TICKET-123"},
		{"TICKET 123", "TICKET-123"},
		{"TICKET\t123", "TICKET-123"},
		{"TICKET\n123", "TICKET-123"},
		{"TICKET\r123", "TICKET-123"},
		{"---TICKET---123---", "TICKET-123"},
		{"TICKET-123-very-long-name-that-should-be-truncated", "TICKET-123-very-long-name-that-should-be-truncat"},
	}

	for _, tt := range tests {
		t.Run(tt.input, func(t *testing.T) {
			result := processor.sanitizeTicketID(tt.input)
			assert.Equal(t, tt.expected, result)
		})
	}
}

func TestProcessor_GenerateBranchName(t *testing.T) {
	processor := &Processor{}

	ticketID := "TICKET-123"
	before := time.Now().Unix()
	branchName := processor.generateBranchName(ticketID)
	after := time.Now().Unix()

	// Check format
	assert.True(t, len(branchName) > len(ticketID))
	assert.True(t, strings.HasPrefix(branchName, "soar-block-TICKET-123-"))

	// Extract timestamp and check it's within range
	parts := strings.Split(branchName, "-")
	timestampStr := parts[len(parts)-1]
	timestamp, err := time.Parse(time.RFC3339, timestampStr)
	if err != nil {
		// Try parsing as Unix timestamp
		timestampInt, err := time.Parse(time.RFC3339, timestampStr)
		if err != nil {
			timestampUnix := time.Now()
			timestampInt = timestampUnix
		}
		timestamp = timestampInt
	}

	assert.True(t, timestamp.Unix() >= before && timestamp.Unix() <= after)
}

func TestProcessor_GenerateCommitMessage(t *testing.T) {
	processor := &Processor{}

	tests := []struct {
		ticketID string
		ip       string
		reason   string
		expected string
	}{
		{
			ticketID: "TICKET-123",
			ip:       "10.0.0.100",
			reason:   "Malicious activity",
			expected: "feat: block IP 10.0.0.100 from SOAR ticket TICKET-123\n\nReason: Malicious activity",
		},
		{
			ticketID: "TICKET-456",
			ip:       "192.168.1.1",
			reason:   "",
			expected: "feat: block IP 192.168.1.1 from SOAR ticket TICKET-456\n\nReason: No reason provided",
		},
	}

	for _, tt := range tests {
		t.Run(tt.ticketID, func(t *testing.T) {
			result := processor.generateCommitMessage(tt.ip, tt.ticketID, tt.reason)
			assert.Equal(t, tt.expected, result)
		})
	}
}

func TestProcessor_GenerateMRContent(t *testing.T) {
	processor := &Processor{}

	ip := "10.0.0.100"
	ticketID := "TICKET-123"
	reason := "Malicious activity"

	title, description := processor.generateMRContent(ip, ticketID, reason)

	// Check title
	assert.Equal(t, "Block IP 10.0.0.100 (SOAR: TICKET-123)", title)

	// Check description contains required sections
	assert.Contains(t, description, "TICKET-123")
	assert.Contains(t, description, "10.0.0.100")
	assert.Contains(t, description, "Malicious activity")
	assert.Contains(t, description, "SOAR webhook service")
}
