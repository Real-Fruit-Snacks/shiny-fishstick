"""Server security configuration for Delta Vision.

This module provides configuration and connection limiting for the WebSocket server
to enhance security and prevent resource exhaustion attacks.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from delta_vision.utils.config import config
from delta_vision.utils.logger import log


@dataclass
class ServerConfig:
    """Security-focused server configuration with sensible defaults."""

    bind_address: str = '127.0.0.1'  # localhost only by default for security
    port: int = 8765
    require_auth: bool = False  # Future: can add authentication
    max_connections: int = 10
    connection_timeout: int = 300  # 5 minutes
    buffer_size: int = None  # Will use config.buffer_size if not specified

    def __post_init__(self):
        """Validate configuration and apply defaults."""
        if self.buffer_size is None:
            self.buffer_size = config.buffer_size

        # Validate bind address
        if not self.bind_address:
            raise ValueError("bind_address cannot be empty")

        # Validate port range
        if not (1 <= self.port <= 65535):
            raise ValueError(f"Port must be between 1 and 65535, got {self.port}")

        # Validate max connections
        if self.max_connections < 1:
            raise ValueError(f"max_connections must be at least 1, got {self.max_connections}")

        # Validate timeout
        if self.connection_timeout < 0:
            raise ValueError(f"connection_timeout cannot be negative, got {self.connection_timeout}")

        # Log security configuration
        if self.bind_address == '0.0.0.0':
            log.warning("Server binding to all interfaces (0.0.0.0) - this exposes the server to the network!")
        elif self.bind_address == '127.0.0.1' or self.bind_address == 'localhost':
            log.info("Server binding to localhost only - secure configuration")
        else:
            log.info(f"Server binding to specific address: {self.bind_address}")


class ConnectionLimiter:
    """Thread-safe connection limiter to prevent resource exhaustion."""

    def __init__(self, max_connections: int = 10):
        """Initialize the connection limiter.

        Args:
            max_connections: Maximum number of concurrent connections allowed
        """
        self.max_connections = max_connections
        self.active_connections = 0
        self._lock = threading.Lock()
        self._connection_ids = set()

    def can_accept_connection(self) -> bool:
        """Check if a new connection can be accepted.

        Returns:
            True if under the connection limit, False otherwise
        """
        with self._lock:
            return self.active_connections < self.max_connections

    def add_connection(self, connection_id: str) -> bool:
        """Register a new connection if under the limit.

        Args:
            connection_id: Unique identifier for the connection

        Returns:
            True if connection was added, False if limit reached
        """
        with self._lock:
            if self.active_connections >= self.max_connections:
                log.warning(f"Connection limit reached ({self.max_connections}), rejecting connection {connection_id}")
                return False

            if connection_id in self._connection_ids:
                log.warning(f"Duplicate connection ID: {connection_id}")
                return False

            self.active_connections += 1
            self._connection_ids.add(connection_id)
            log.debug(f"Connection added: {connection_id} (active: {self.active_connections}/{self.max_connections})")
            return True

    def remove_connection(self, connection_id: str) -> None:
        """Remove a connection from tracking.

        Args:
            connection_id: Unique identifier for the connection
        """
        with self._lock:
            if connection_id in self._connection_ids:
                self.active_connections -= 1
                self._connection_ids.remove(connection_id)
                active = self.active_connections
                max_conn = self.max_connections
                log.debug(f"Connection removed: {connection_id} (active: {active}/{max_conn})")
            else:
                log.warning(f"Attempted to remove unknown connection: {connection_id}")

    def get_active_count(self) -> int:
        """Get the current number of active connections.

        Returns:
            Number of active connections
        """
        with self._lock:
            return self.active_connections

    def reset(self) -> None:
        """Reset all connection tracking (use with caution)."""
        with self._lock:
            self.active_connections = 0
            self._connection_ids.clear()
            log.info("Connection limiter reset")


# Default server configuration (secure by default)
default_server_config = ServerConfig()
