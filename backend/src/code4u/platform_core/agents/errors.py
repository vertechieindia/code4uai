from __future__ import annotations
"""Pipeline errors: fail loudly, never fake success."""


class PipelineIncompleteError(Exception):
    """Raised when a required pipeline step is not implemented. Do not swallow."""
    def __init__(self, message: str = "Pipeline step not implemented"):
        self.message = message
        super().__init__(self.message)
