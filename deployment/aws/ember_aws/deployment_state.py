"""DeploymentState enum: lifecycle states for an ember deployment."""

from __future__ import annotations

from enum import StrEnum


class DeploymentState(StrEnum):
    """Lifecycle state of an ember deployment.

    Attributes
    ----------
    ABSENT : str
        No stack exists.
    CREATING : str
        Stack creation in progress.
    RUNNING : str
        Instance is running and healthy.
    STOPPING : str
        Instance stop in progress.
    STOPPED : str
        Instance is stopped.
    UPDATING : str
        In-place update in progress.
    REPLACING : str
        Instance replacement in progress.
    DESTROYING : str
        Stack deletion in progress.
    FAILED : str
        Stack or instance is in a failed state.
    """

    ABSENT = "absent"
    CREATING = "creating"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    UPDATING = "updating"
    REPLACING = "replacing"
    DESTROYING = "destroying"
    FAILED = "failed"
