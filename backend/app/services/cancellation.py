"""Cancellation registry for briefing generation.

Provides an asyncio.Event-based mechanism to immediately cancel in-flight
LLM and TTS HTTP requests when a user cancels a briefing.
"""

import asyncio
from typing import TypeVar

T = TypeVar("T")

# Briefing generation exceptions (moved here to avoid circular imports)


class BriefingCancelledException(Exception):
    """Raised when a briefing generation is cancelled by the user."""
    pass


class BriefingTimeoutException(Exception):
    """Raised when a briefing generation exceeds the timeout."""
    pass


# Registry of cancellation events keyed by briefing_id
_cancel_events: dict[str, asyncio.Event] = {}


def register(briefing_id: str) -> asyncio.Event:
    """Register a cancellation event for a briefing generation.

    Called at the start of briefing generation.
    Returns the event (mainly for testing).
    """
    event = asyncio.Event()
    _cancel_events[briefing_id] = event
    return event


def signal(briefing_id: str) -> bool:
    """Signal cancellation for a briefing.

    Called by the cancel endpoint to immediately abort in-flight requests.
    Returns True if an event was found and signalled.
    """
    event = _cancel_events.get(briefing_id)
    if event is not None:
        event.set()
        print(f"[Cancellation] Signalled cancellation for briefing {briefing_id}")
        return True
    return False


def unregister(briefing_id: str) -> None:
    """Remove the cancellation event for a briefing.

    Called in the finally block of briefing generation to clean up.
    """
    _cancel_events.pop(briefing_id, None)


def is_cancelled(briefing_id: str) -> bool:
    """Check if a briefing has been cancelled via the event.

    Fast synchronous check - no DB query needed.
    """
    event = _cancel_events.get(briefing_id)
    return event is not None and event.is_set()


async def cancellable_await(coro, briefing_id: str) -> T:
    """Race an awaitable against the cancellation event.

    If the cancellation event fires before the coroutine completes,
    the coroutine's task is cancelled and BriefingCancelledException is raised.

    If no cancellation event is registered for this briefing_id,
    the coroutine runs normally.

    Args:
        coro: The coroutine to await (e.g., an httpx POST request).
        briefing_id: The briefing ID to check for cancellation.

    Returns:
        The result of the coroutine.

    Raises:
        BriefingCancelledException: If cancellation is signalled.
    """
    event = _cancel_events.get(briefing_id)

    # No event registered - run normally
    if event is None:
        return await coro

    # Already cancelled - don't even start
    if event.is_set():
        raise BriefingCancelledException("Briefing was cancelled by user")

    # Race the coroutine against the cancellation event
    task = asyncio.create_task(coro)
    cancel_waiter = asyncio.create_task(event.wait())

    done, pending = await asyncio.wait(
        {task, cancel_waiter},
        return_when=asyncio.FIRST_COMPLETED,
    )

    if cancel_waiter in done:
        # Cancellation fired - kill the in-flight request
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        raise BriefingCancelledException("Briefing was cancelled by user")

    # Coroutine finished first - clean up the cancel waiter
    cancel_waiter.cancel()
    try:
        await cancel_waiter
    except asyncio.CancelledError:
        pass

    return task.result()
