package workflow

import (
	"net"
	"net/netip"
	"time"

	"go.temporal.io/sdk/workflow"

	"launchpad.net/maas/maas/src/maasagent/internal/netmon"
)

// CheckIPParam is a workflow parameter for the CheckIP workflow
type CheckIPParam struct {
	IPs []netip.Addr
}

// CheckIPResult is a value returned by the CheckIP workflow
type CheckIPResult struct {
	IPs map[netip.Addr]net.HardwareAddr
}

// CheckIP is a Temporal workflow for checking available IP addresses
func CheckIP(ctx workflow.Context, param CheckIPParam) (CheckIPResult, error) {
	ao := workflow.LocalActivityOptions{
		StartToCloseTimeout: 10 * time.Second,
	}
	ctx = workflow.WithLocalActivityOptions(ctx, ao)

	var scanned map[netip.Addr]net.HardwareAddr

	err := workflow.ExecuteLocalActivity(ctx, netmon.Scan, param.IPs).Get(ctx, &scanned)
	if err != nil {
		return CheckIPResult{}, err
	}

	result := CheckIPResult{
		IPs: scanned,
	}

	return result, nil
}