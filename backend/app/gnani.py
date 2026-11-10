"""Shared request gate for Gnani accounts limited to one active call."""

import asyncio

request_lock = asyncio.Lock()
