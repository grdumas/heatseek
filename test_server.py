"""
Test script for HeatSeek v2.0 server logic

Tests the coverage analysis logic with mock data
"""

import sys
from datetime import datetime

# Mock data structure mimicking OpenSearch results
MOCK_OPENSEARCH_DATA = [
    {
        "_source": {
            "metadata": {
                "cloud_provider": "AWS",
                "instance_type": "m5.24xlarge",
                "test_timestamp": "2026-05-01T10:00:00"
            },
            "system_under_test": {
                "hardware": {
                    "cpu": {
                        "model": "Intel Xeon Platinum 8259CL",
                        "architecture": "x86_64"
                    }
                },
                "operating_system": {
                    "version": "RHEL-9.3"
                }
            },
            "test": {
                "name": "coremark"
            }
        }
    },
    {
        "_source": {
            "metadata": {
                "cloud_provider": "AWS",
                "instance_type": "m5.24xlarge",
                "test_timestamp": "2026-05-15T10:00:00"
            },
            "system_under_test": {
                "hardware": {
                    "cpu": {
                        "model": "Intel Xeon Platinum 8259CL",
                        "architecture": "x86_64"
                    }
                },
                "operating_system": {
                    "version": "RHEL-9.4"
                }
            },
            "test": {
                "name": "coremark"
            }
        }
    },
    {
        "_source": {
            "metadata": {
                "cloud_provider": "Azure",
                "instance_type": "Standard_D4s_v5",
                "test_timestamp": "2026-05-10T10:00:00"
            },
            "system_under_test": {
                "hardware": {
                    "cpu": {
                        "model": "AMD EPYC 7763",
                        "architecture": "x86_64"
                    }
                },
                "operating_system": {
                    "version": "RHEL-9.3"
                }
            },
            "test": {
                "name": "pyperf"
            }
        }
    },
    {
        "_source": {
            "metadata": {
                "cloud_provider": "GCP",
                "instance_type": "n2-standard-32",
                "test_timestamp": "2026-05-20T10:00:00"
            },
            "system_under_test": {
                "hardware": {
                    "cpu": {
                        "model": "Intel Ice Lake",
                        "architecture": "x86_64"
                    }
                },
                "operating_system": {
                    "version": "RHEL-9.2"
                }
            },
            "test": {
                "name": "streams"
            }
        }
    }
]

def test_coverage_matrix():
    """Test coverage matrix building logic"""
    from server import build_coverage_matrix, calculate_summary

    print("Testing coverage matrix building...")
    matrix = build_coverage_matrix(MOCK_OPENSEARCH_DATA)

    # Verify platforms
    assert "AWS" in matrix, "AWS platform should be in matrix"
    assert "Azure" in matrix, "Azure platform should be in matrix"
    assert "GCP" in matrix, "GCP platform should be in matrix"

    # Check AWS coverage
    aws_cells = matrix["AWS"]
    assert len(aws_cells) == 1, f"Expected 1 AWS cell, got {len(aws_cells)}"

    aws_cell = aws_cells[0]
    assert aws_cell.system == "m5.24xlarge"
    assert aws_cell.benchmark == "coremark"
    assert len(aws_cell.os_builds) == 2, f"Expected 2 OS builds, got {len(aws_cell.os_builds)}"
    assert "RHEL-9.3" in aws_cell.os_builds
    assert "RHEL-9.4" in aws_cell.os_builds
    assert aws_cell.viable_for_regression == True, "Should be viable with 2+ builds"
    assert aws_cell.color_code == "#A5D6A7", f"Expected light green, got {aws_cell.color_code}"

    print("✓ Coverage matrix building works correctly")

    # Test summary calculation
    print("\nTesting summary calculation...")
    summary = calculate_summary(matrix)

    assert summary["total_combinations"] == 3, f"Expected 3 combinations, got {summary['total_combinations']}"
    assert summary["viable_combinations"] == 1, f"Expected 1 viable, got {summary['viable_combinations']}"
    assert summary["coverage_score"] == 33.3, f"Expected 33.3%, got {summary['coverage_score']}"

    print("✓ Summary calculation works correctly")
    print(f"\nSummary:")
    print(f"  Coverage Score: {summary['coverage_score']}%")
    print(f"  Total Combinations: {summary['total_combinations']}")
    print(f"  Viable Combinations: {summary['viable_combinations']}")
    print(f"  Critical Gaps: {summary['critical_gaps']}")
    print(f"  Recommended Systems: {summary['recommended_systems']}")

def test_color_codes():
    """Test color coding logic"""
    from server import CoverageCell

    print("\nTesting color codes...")

    # Test all color thresholds
    test_cases = [
        (0, "#E0E0E0", "Gray"),
        (1, "#FFF59D", "Yellow"),
        (2, "#A5D6A7", "Light green"),
        (3, "#66BB6A", "Green"),
        (4, "#66BB6A", "Green"),
        (5, "#2E7D32", "Dark green"),
        (10, "#2E7D32", "Dark green")
    ]

    for count, expected_color, name in test_cases:
        cell = CoverageCell(
            platform="test",
            system="test",
            benchmark="test",
            os_builds=set([f"RHEL-{i}" for i in range(count)]),
            cpu_info="test",
            architecture="x86_64"
        )
        assert cell.color_code == expected_color, \
            f"Build count {count} should be {name} ({expected_color}), got {cell.color_code}"

    print("✓ All color codes correct")

def test_viable_for_regression():
    """Test regression viability logic"""
    from server import CoverageCell

    print("\nTesting regression viability...")

    # 0 builds - not viable
    cell = CoverageCell("test", "test", "test", set(), "test", "x86_64")
    assert cell.viable_for_regression == False

    # 1 build - not viable
    cell = CoverageCell("test", "test", "test", {"RHEL-9.3"}, "test", "x86_64")
    assert cell.viable_for_regression == False

    # 2 builds - viable
    cell = CoverageCell("test", "test", "test", {"RHEL-9.3", "RHEL-9.4"}, "test", "x86_64")
    assert cell.viable_for_regression == True

    # 3+ builds - viable
    cell = CoverageCell("test", "test", "test", {"RHEL-9.2", "RHEL-9.3", "RHEL-9.4"}, "test", "x86_64")
    assert cell.viable_for_regression == True

    print("✓ Regression viability logic correct")

def test_cell_serialization():
    """Test CoverageCell to_dict() conversion"""
    from server import CoverageCell

    print("\nTesting cell serialization...")

    cell = CoverageCell(
        platform="AWS",
        system="m5.24xlarge",
        benchmark="coremark",
        os_builds={"RHEL-9.3", "RHEL-9.4"},
        cpu_info="Intel Xeon",
        architecture="x86_64"
    )

    data = cell.to_dict()

    assert data["platform"] == "AWS"
    assert data["system"] == "m5.24xlarge"
    assert data["benchmark"] == "coremark"
    assert len(data["os_builds"]) == 2
    assert data["build_count"] == 2
    assert data["viable"] == True
    assert data["color"] == "#A5D6A7"
    assert isinstance(data["os_builds"], list), "os_builds should be a list"

    print("✓ Cell serialization works correctly")

if __name__ == "__main__":
    print("=" * 60)
    print("HeatSeek v2.0 Server Logic Tests")
    print("=" * 60)

    try:
        test_color_codes()
        test_viable_for_regression()
        test_cell_serialization()
        test_coverage_matrix()

        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        sys.exit(0)

    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
