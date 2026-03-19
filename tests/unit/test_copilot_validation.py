"""Tests for copilot-setup-steps.yml constraint validation."""

from __future__ import annotations

from rkp.projection.adapters.copilot import validate_setup_steps


class TestSetupStepsValidation:
    def test_valid_setup_steps(self) -> None:
        """Valid setup-steps returns empty error list."""
        content = {
            "name": "Copilot Setup Steps",
            "on": "workflow_dispatch",
            "jobs": {
                "copilot-setup-steps": {
                    "runs-on": "ubuntu-latest",
                    "timeout-minutes": 30,
                    "steps": [
                        {"uses": "actions/checkout@v4"},
                        {"uses": "actions/setup-python@v5", "with": {"python-version": "3.12"}},
                    ],
                }
            },
        }

        errors = validate_setup_steps(content)
        assert errors == []

    def test_missing_jobs(self) -> None:
        """Missing 'jobs' key produces error."""
        errors = validate_setup_steps({"name": "test"})
        assert len(errors) == 1
        assert "Missing 'jobs' key" in errors[0]

    def test_multiple_jobs(self) -> None:
        """Multiple jobs produces error."""
        content = {
            "jobs": {
                "copilot-setup-steps": {"runs-on": "ubuntu-latest"},
                "other-job": {"runs-on": "ubuntu-latest"},
            }
        }

        errors = validate_setup_steps(content)
        assert any("exactly 1 job" in e for e in errors)

    def test_wrong_job_name(self) -> None:
        """Wrong job name produces error."""
        content = {
            "jobs": {
                "wrong-name": {
                    "runs-on": "ubuntu-latest",
                    "timeout-minutes": 30,
                    "steps": [],
                }
            }
        }

        errors = validate_setup_steps(content)
        assert any("copilot-setup-steps" in e and "wrong-name" in e for e in errors)

    def test_timeout_exceeds_59(self) -> None:
        """Timeout > 59 produces error."""
        content = {
            "jobs": {
                "copilot-setup-steps": {
                    "runs-on": "ubuntu-latest",
                    "timeout-minutes": 60,
                    "steps": [],
                }
            }
        }

        errors = validate_setup_steps(content)
        assert any("timeout-minutes" in e and "60" in e for e in errors)

    def test_timeout_at_59_is_valid(self) -> None:
        """Timeout at exactly 59 is valid."""
        content = {
            "jobs": {
                "copilot-setup-steps": {
                    "runs-on": "ubuntu-latest",
                    "timeout-minutes": 59,
                    "steps": [],
                }
            }
        }

        errors = validate_setup_steps(content)
        assert not any("timeout" in e for e in errors)

    def test_unsupported_services_key(self) -> None:
        """'services' key at job level produces error."""
        content = {
            "jobs": {
                "copilot-setup-steps": {
                    "runs-on": "ubuntu-latest",
                    "timeout-minutes": 30,
                    "services": {"postgres": {"image": "postgres:15"}},
                    "steps": [],
                }
            }
        }

        errors = validate_setup_steps(content)
        assert any("services" in e for e in errors)

    def test_unsupported_container_key(self) -> None:
        """'container' key at job level produces error."""
        content = {
            "jobs": {
                "copilot-setup-steps": {
                    "runs-on": "ubuntu-latest",
                    "container": {"image": "python:3.12"},
                    "steps": [],
                }
            }
        }

        errors = validate_setup_steps(content)
        assert any("container" in e for e in errors)

    def test_unsupported_strategy_key(self) -> None:
        """'strategy' key at job level produces error."""
        content = {
            "jobs": {
                "copilot-setup-steps": {
                    "runs-on": "ubuntu-latest",
                    "strategy": {"matrix": {"python": ["3.11", "3.12"]}},
                    "steps": [],
                }
            }
        }

        errors = validate_setup_steps(content)
        assert any("strategy" in e for e in errors)

    def test_unsupported_needs_key(self) -> None:
        """'needs' key at job level produces error."""
        content = {
            "jobs": {
                "copilot-setup-steps": {
                    "runs-on": "ubuntu-latest",
                    "needs": ["other-job"],
                    "steps": [],
                }
            }
        }

        errors = validate_setup_steps(content)
        assert any("needs" in e for e in errors)

    def test_unsupported_outputs_key(self) -> None:
        """'outputs' key at job level produces error."""
        content = {
            "jobs": {
                "copilot-setup-steps": {
                    "runs-on": "ubuntu-latest",
                    "outputs": {"result": "${{ steps.step1.outputs.result }}"},
                    "steps": [],
                }
            }
        }

        errors = validate_setup_steps(content)
        assert any("outputs" in e for e in errors)

    def test_jobs_not_a_mapping(self) -> None:
        """'jobs' as a non-mapping produces error."""
        errors = validate_setup_steps({"jobs": "not-a-dict"})
        assert any("mapping" in e for e in errors)

    def test_job_not_a_mapping(self) -> None:
        """Job value as a non-mapping produces error."""
        errors = validate_setup_steps({"jobs": {"copilot-setup-steps": "not-a-dict"}})
        assert any("mapping" in e for e in errors)

    def test_steps_not_a_list(self) -> None:
        """'steps' as a non-list produces error."""
        content = {
            "jobs": {
                "copilot-setup-steps": {
                    "runs-on": "ubuntu-latest",
                    "steps": "not-a-list",
                }
            }
        }

        errors = validate_setup_steps(content)
        assert any("list" in e for e in errors)

    def test_unpinned_action_warning(self) -> None:
        """Unpinned action version produces error."""
        content = {
            "jobs": {
                "copilot-setup-steps": {
                    "runs-on": "ubuntu-latest",
                    "steps": [{"uses": "actions/checkout"}],
                }
            }
        }

        errors = validate_setup_steps(content)
        assert any("pinned" in e for e in errors)

    def test_step_not_a_mapping(self) -> None:
        """Non-mapping step produces error."""
        content = {
            "jobs": {
                "copilot-setup-steps": {
                    "runs-on": "ubuntu-latest",
                    "steps": ["not-a-dict"],
                }
            }
        }

        errors = validate_setup_steps(content)
        assert any("mapping" in e for e in errors)

    def test_zero_timeout(self) -> None:
        """Zero timeout produces error."""
        content = {
            "jobs": {
                "copilot-setup-steps": {
                    "runs-on": "ubuntu-latest",
                    "timeout-minutes": 0,
                    "steps": [],
                }
            }
        }

        errors = validate_setup_steps(content)
        assert any("positive" in e for e in errors)
