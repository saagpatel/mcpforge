"""Session-scoped, authenticated MCP cursors (opaque, not encrypted)."""

import base64
import binascii
import hashlib
import hmac
import json
from typing import Any

from mcpforge.pagination.history import TraversalHistory


class InvalidCursorError(ValueError):
    """An invalid client cursor maps to JSON-RPC Invalid params."""

    code = -32602

    def to_jsonrpc_error(self) -> dict[str, Any]:
        return {"code": self.code, "message": "Invalid params: invalid pagination cursor"}


class CursorCodec:
    """Sign base64url JSON. Callers own the key and its session lifetime.

    Clients must neither interpret cursors nor persist them across sessions.
    Authentication does not hide sensitive state; do not put secrets in cursors.
    Retain this codec or explicitly share its history across resumed calls;
    reconstructing only the signing key does not restore traversal history.
    """

    version = 1

    def __init__(self, key: bytes, *, history: TraversalHistory | None = None):
        if not isinstance(key, bytes) or not key:
            raise ValueError("a nonempty bytes signing key is required")
        self._key = key
        self.history = history if history is not None else TraversalHistory()

    @staticmethod
    def _encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

    @classmethod
    def _decode(cls, value: str) -> bytes:
        decoded = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
        if cls._encode(decoded) != value:
            raise ValueError("noncanonical base64url")
        return decoded

    def encode(self, state: dict[str, Any]) -> str:
        if not isinstance(state, dict):
            raise ValueError("cursor state must be an object")
        payload = json.dumps(
            {"version": self.version, "state": state},
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
        tag = hmac.digest(self._key, payload, hashlib.sha256)
        return f"{self._encode(payload)}.{self._encode(tag)}"

    def decode(self, cursor: str) -> dict[str, Any]:
        try:
            if not isinstance(cursor, str):
                raise ValueError("invalid cursor type")
            body, signature = cursor.split(".")
            payload, tag = self._decode(body), self._decode(signature)
            if not hmac.compare_digest(tag, hmac.digest(self._key, payload, hashlib.sha256)):
                raise ValueError("invalid cursor signature")
            document = json.loads(payload)
            if (
                not isinstance(document, dict)
                or set(document) != {"version", "state"}
                or type(document["version"]) is not int
                or document["version"] != self.version
                or not isinstance(document["state"], dict)
            ):
                raise ValueError("invalid cursor envelope")
            return document["state"]
        except (ValueError, TypeError, UnicodeError, binascii.Error, RecursionError) as exc:
            raise InvalidCursorError("invalid pagination cursor") from exc
