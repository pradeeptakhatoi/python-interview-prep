"""
asyncio Producer/Consumer with Backpressure

Demonstrates:
- asyncio.Queue for decoupled producer/consumer
- Bounded queue as backpressure mechanism
- TaskGroup for structured lifecycle management
- Graceful shutdown with sentinel values
- Cancellation handling in consumers
"""

from __future__ import annotations
import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator


# =============================================================================
# Basic: Single producer, single consumer
# =============================================================================
async def basic_example():
    queue: asyncio.Queue[int | None] = asyncio.Queue(maxsize=5)  # bounded = backpressure

    async def producer():
        for i in range(15):
            print(f"  producing {i} (queue size: {queue.qsize()}/{queue.maxsize})")
            await queue.put(i)    # blocks if queue is full — natural backpressure
        await queue.put(None)     # sentinel to signal completion

    async def consumer():
        while True:
            item = await queue.get()
            if item is None:
                queue.task_done()
                break
            await asyncio.sleep(0.05)   # simulate work
            print(f"    consumed {item}")
            queue.task_done()

    await asyncio.gather(producer(), consumer())
    print("  Basic example complete\n")


# =============================================================================
# Advanced: Multiple producers, multiple consumers, metrics, graceful shutdown
# =============================================================================
@dataclass
class WorkItem:
    id: int
    payload: str
    created_at: float = field(default_factory=time.monotonic)


@dataclass
class ProcessingMetrics:
    produced: int = 0
    consumed: int = 0
    errors: int = 0
    total_latency: float = 0.0

    @property
    def avg_latency_ms(self) -> float:
        if self.consumed == 0:
            return 0.0
        return (self.total_latency / self.consumed) * 1000


class Pipeline:
    """
    Bounded async pipeline with multiple producers and consumers.

    Backpressure: producers block when queue reaches maxsize.
    Shutdown: producers put sentinel objects; consumers exit on sentinel.
    """

    _SENTINEL = object()  # unique sentinel — identity check, not equality

    def __init__(self, queue_size: int = 10):
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=queue_size)
        self._metrics = ProcessingMetrics()
        self._shutdown = asyncio.Event()

    async def producer(self, producer_id: int, n_items: int) -> None:
        """Produce n_items then put a sentinel."""
        try:
            for i in range(n_items):
                if self._shutdown.is_set():
                    break
                item = WorkItem(
                    id=producer_id * 1000 + i,
                    payload=f"data-{producer_id}-{i}"
                )
                await self._queue.put(item)
                self._metrics.produced += 1
                # Simulate variable production rate:
                await asyncio.sleep(random.uniform(0.01, 0.05))
        finally:
            await self._queue.put(self._SENTINEL)

    async def consumer(self, consumer_id: int) -> None:
        """Consume until sentinel is received."""
        while True:
            try:
                item = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=2.0
                )
            except TimeoutError:
                # No items in 2 seconds — check if we should shut down
                if self._shutdown.is_set() and self._queue.empty():
                    return
                continue

            if item is self._SENTINEL:
                self._queue.task_done()
                return  # this consumer's done

            try:
                await self._process(item, consumer_id)
            except Exception as e:
                self._metrics.errors += 1
                print(f"  [Consumer {consumer_id}] Error processing {item.id}: {e}")
            finally:
                self._queue.task_done()

    async def _process(self, item: WorkItem, consumer_id: int) -> None:
        latency = time.monotonic() - item.created_at
        await asyncio.sleep(random.uniform(0.02, 0.08))  # simulate work
        self._metrics.consumed += 1
        self._metrics.total_latency += latency
        print(f"  [Consumer {consumer_id}] processed {item.id} "
              f"(latency: {latency*1000:.1f}ms, queue: {self._queue.qsize()})")

    async def run(
        self,
        n_producers: int = 2,
        n_consumers: int = 3,
        items_per_producer: int = 5
    ) -> ProcessingMetrics:
        """Run the pipeline using TaskGroup for structured concurrency."""

        async with asyncio.TaskGroup() as tg:
            # Start consumers first:
            for i in range(n_consumers):
                tg.create_task(self.consumer(i))

            # Start producers:
            for i in range(n_producers):
                tg.create_task(self.producer(i, items_per_producer))

            # Wait for producers to finish, then signal shutdown
            # (TaskGroup waits for ALL tasks; consumers exit via sentinel)

        self._shutdown.set()
        return self._metrics


# =============================================================================
# Pattern: Async generator as data source (pull-based)
# =============================================================================
async def async_data_source(n: int) -> AsyncIterator[WorkItem]:
    """Pull-based alternative to queue-based producer."""
    for i in range(n):
        await asyncio.sleep(0.01)
        yield WorkItem(id=i, payload=f"item-{i}")


async def process_stream(source: AsyncIterator[WorkItem], concurrency: int = 5) -> int:
    """Process items from an async generator with bounded concurrency."""
    semaphore = asyncio.Semaphore(concurrency)  # limit concurrent tasks

    async def bounded_process(item: WorkItem) -> None:
        async with semaphore:
            await asyncio.sleep(random.uniform(0.01, 0.05))
            print(f"  processed stream item {item.id}")

    tasks = []
    async for item in source:
        task = asyncio.create_task(bounded_process(item))
        tasks.append(task)

    results = await asyncio.gather(*tasks, return_exceptions=True)
    errors = sum(1 for r in results if isinstance(r, Exception))
    return len(results) - errors


# =============================================================================
# Pattern: Dead letter queue for failed items
# =============================================================================
class PipelineWithDLQ:
    """Pipeline that routes failed items to a dead letter queue."""

    def __init__(self, max_retries: int = 3):
        self._queue: asyncio.Queue[WorkItem] = asyncio.Queue(maxsize=20)
        self._dlq: asyncio.Queue[tuple[WorkItem, Exception]] = asyncio.Queue()
        self._max_retries = max_retries

    async def consumer_with_retry(self, consumer_id: int) -> None:
        retry_counts: dict[int, int] = {}

        while True:
            item: WorkItem | object = await self._queue.get()
            if item is None:   # simple sentinel for this example
                self._queue.task_done()
                return

            assert isinstance(item, WorkItem)
            retries = retry_counts.get(item.id, 0)

            try:
                if random.random() < 0.3:  # simulate 30% failure rate
                    raise ValueError(f"Processing failed for {item.id}")
                print(f"  [Consumer {consumer_id}] OK: {item.id}")
                retry_counts.pop(item.id, None)

            except Exception as e:
                if retries < self._max_retries:
                    retry_counts[item.id] = retries + 1
                    print(f"  [Consumer {consumer_id}] Retry {retries+1}/{self._max_retries} for {item.id}")
                    await asyncio.sleep(0.1 * (2 ** retries))  # exponential backoff
                    await self._queue.put(item)                  # re-queue
                else:
                    print(f"  [Consumer {consumer_id}] DLQ: {item.id} after {retries} retries")
                    await self._dlq.put((item, e))
                    retry_counts.pop(item.id, None)
            finally:
                self._queue.task_done()


# =============================================================================
# Main
# =============================================================================
async def main():
    print("=== Basic Producer/Consumer ===")
    await basic_example()

    print("=== Multi-Producer/Consumer Pipeline ===")
    pipeline = Pipeline(queue_size=8)
    metrics = await pipeline.run(
        n_producers=2,
        n_consumers=3,
        items_per_producer=6
    )
    print(f"\nMetrics: produced={metrics.produced}, consumed={metrics.consumed}, "
          f"errors={metrics.errors}, avg_latency={metrics.avg_latency_ms:.1f}ms")

    print("\n=== Async Generator Stream Processing ===")
    source = async_data_source(10)
    ok = await process_stream(source, concurrency=3)
    print(f"Processed {ok} items successfully")


if __name__ == '__main__':
    asyncio.run(main())
