# Event-Driven Architecture with asyncio

## Concept

Event-driven architecture (EDA) decouples components through events: producers emit events, consumers react. In Python, asyncio provides the primitives (`Queue`, `Event`, `Condition`) and the concurrency model (cooperative multitasking via coroutines) to implement EDA efficiently in a single process.

### asyncio.Queue — The Core Building Block

```python
import asyncio
from dataclasses import dataclass, field
from typing import Any

@dataclass
class Event:
    topic: str
    payload: Any
    timestamp: float = field(default_factory=asyncio.get_event_loop().time)

class EventBus:
    """In-process pub/sub using asyncio.Queue per subscriber."""

    def __init__(self):
        self._subscribers: dict[str, list[asyncio.Queue]] = {}

    def subscribe(self, topic: str, maxsize: int = 0) -> asyncio.Queue:
        """Returns a queue that receives events for the given topic."""
        q: asyncio.Queue[Event] = asyncio.Queue(maxsize=maxsize)
        self._subscribers.setdefault(topic, []).append(q)
        return q

    def unsubscribe(self, topic: str, queue: asyncio.Queue) -> None:
        subs = self._subscribers.get(topic, [])
        try:
            subs.remove(queue)
        except ValueError:
            pass

    async def publish(self, topic: str, payload: Any) -> None:
        event = Event(topic=topic, payload=payload)
        subscribers = self._subscribers.get(topic, [])
        if not subscribers:
            return
        # Fan out to all subscribers concurrently:
        await asyncio.gather(
            *(q.put(event) for q in subscribers),
            return_exceptions=True,
        )

# Usage:
async def main():
    bus = EventBus()
    order_queue = bus.subscribe("order.created")
    email_queue = bus.subscribe("order.created")

    async def order_processor():
        while True:
            event = await order_queue.get()
            print(f"Processing order: {event.payload}")
            order_queue.task_done()

    async def email_sender():
        while True:
            event = await email_queue.get()
            print(f"Sending email for: {event.payload}")
            email_queue.task_done()

    async with asyncio.TaskGroup() as tg:
        tg.create_task(order_processor())
        tg.create_task(email_sender())
        await bus.publish("order.created", {"id": 123, "item": "Widget"})
        await asyncio.sleep(0.1)  # let tasks process
```

### Producer-Consumer with Backpressure

```python
import asyncio

async def producer(queue: asyncio.Queue, items: list):
    """Respects backpressure — blocks when queue is full."""
    for item in items:
        await queue.put(item)   # blocks if queue is full (maxsize reached)
        print(f"Produced: {item}")
    await queue.put(None)  # sentinel

async def consumer(queue: asyncio.Queue, worker_id: int):
    """Process items until sentinel received."""
    while True:
        item = await queue.get()
        if item is None:
            await queue.put(None)  # pass sentinel to next consumer
            break
        await asyncio.sleep(0.1)  # simulate I/O work
        print(f"Worker {worker_id} consumed: {item}")
        queue.task_done()

async def pipeline():
    queue: asyncio.Queue[int | None] = asyncio.Queue(maxsize=5)  # bounded!

    async with asyncio.TaskGroup() as tg:
        tg.create_task(producer(queue, list(range(20))))
        for i in range(3):  # 3 concurrent consumers
            tg.create_task(consumer(queue, i))

    await queue.join()  # wait for all items to be processed
```

### Event-Driven State Machine

```python
import asyncio
from enum import Enum, auto

class OrderState(Enum):
    PENDING = auto()
    PROCESSING = auto()
    SHIPPED = auto()
    DELIVERED = auto()
    CANCELLED = auto()

class Order:
    def __init__(self, order_id: str):
        self.order_id = order_id
        self.state = OrderState.PENDING
        self._state_changed = asyncio.Event()
        self._transitions = {
            OrderState.PENDING: {OrderState.PROCESSING, OrderState.CANCELLED},
            OrderState.PROCESSING: {OrderState.SHIPPED, OrderState.CANCELLED},
            OrderState.SHIPPED: {OrderState.DELIVERED},
            OrderState.DELIVERED: set(),
            OrderState.CANCELLED: set(),
        }

    def transition(self, new_state: OrderState) -> None:
        allowed = self._transitions[self.state]
        if new_state not in allowed:
            raise ValueError(
                f"Cannot transition from {self.state} to {new_state}. "
                f"Allowed: {allowed}"
            )
        self.state = new_state
        self._state_changed.set()
        self._state_changed.clear()

    async def wait_for_state(self, target: OrderState) -> None:
        """Asynchronously wait until order reaches target state."""
        while self.state != target:
            await self._state_changed.wait()

async def shipping_service(order: Order):
    await order.wait_for_state(OrderState.PROCESSING)
    await asyncio.sleep(1)  # simulate shipping API call
    order.transition(OrderState.SHIPPED)
```

### Async Iterator as Event Stream

```python
import asyncio
from typing import AsyncIterator

class EventStream:
    """Yields events as an async iterator — consumable in async for loops."""

    def __init__(self, source_queue: asyncio.Queue):
        self._queue = source_queue

    def __aiter__(self) -> 'EventStream':
        return self

    async def __anext__(self) -> Event:
        event = await self._queue.get()
        if event is None:  # sentinel
            raise StopAsyncIteration
        return event

async def process_stream(stream: EventStream):
    async for event in stream:
        match event.topic:
            case "order.created":
                await handle_order_created(event)
            case "order.shipped":
                await handle_order_shipped(event)
            case _:
                pass  # unknown topic — ignore
```

### Timeout and Cancellation

```python
import asyncio

async def process_with_timeout(queue: asyncio.Queue, timeout: float = 5.0):
    """Process events until timeout of inactivity."""
    while True:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=timeout)
            await handle_event(event)
        except asyncio.TimeoutError:
            print(f"No events for {timeout}s — shutting down")
            break
        except asyncio.CancelledError:
            print("Processor cancelled — cleanup")
            raise  # always re-raise CancelledError

async def main():
    queue = asyncio.Queue()
    task = asyncio.create_task(process_with_timeout(queue, timeout=2.0))

    await queue.put(Event("ping", {}))
    await asyncio.sleep(3)  # longer than timeout

    # Task will have finished itself; if not, cancel cleanly:
    if not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
```

---

## Interview Questions

### Q1: How does asyncio's cooperative multitasking model differ from OS threading for event-driven systems?

**Model answer:**
asyncio uses a single-threaded event loop with cooperative multitasking. Tasks voluntarily yield control at `await` points. There is no preemption — a task runs until it awaits.

**Advantages over threads for EDA:**
- **No shared-state races:** only one coroutine runs at a time — no need for locks around in-memory data structures (dict, list).
- **Lower overhead:** 10k+ coroutines are practical; 10k threads are not (each thread costs ~1MB stack, context switches are expensive).
- **Explicit yield points:** concurrency points are visible in code (`await`), reducing reasoning complexity.

**Limitations:**
- **CPU-bound work blocks the loop:** a single CPU-intensive coroutine blocks ALL other coroutines. Solution: `loop.run_in_executor()` or `asyncio.to_thread()`.
- **No true parallelism for CPU work:** use `ProcessPoolExecutor` for CPU.
- **Blocking calls kill throughput:** any `time.sleep()`, synchronous I/O, or non-async library call blocks the entire loop.

```python
# BAD: blocks the event loop
async def blocking_handler(event):
    time.sleep(1)  # blocks ALL coroutines for 1 second!
    return process(event.payload)

# GOOD: offload blocking work
async def non_blocking_handler(event):
    result = await asyncio.to_thread(cpu_heavy, event.payload)
    return result
```

### Q2: How do you handle backpressure in an asyncio event-driven system?

**Model answer:**
Backpressure is pressure propagated upstream when a consumer is slower than a producer. In asyncio:

```python
# asyncio.Queue(maxsize=N) provides built-in backpressure:
queue: asyncio.Queue = asyncio.Queue(maxsize=100)

# Producer blocks when queue is full:
await queue.put(item)   # suspends if queue at capacity — backpressure!

# Alternative: non-blocking with overflow strategy:
try:
    queue.put_nowait(item)   # raises QueueFull if full
except asyncio.QueueFull:
    match overflow_policy:
        case "drop_oldest":
            try:
                queue.get_nowait()   # discard oldest
            except asyncio.QueueEmpty:
                pass
            queue.put_nowait(item)  # retry
        case "drop_newest":
            pass  # discard current item
        case "error":
            raise
```

For external queues (Kafka, Redis Streams): acknowledge/commit only after successful processing. Don't ACK before handling — unhandled events will be re-delivered.

### Q3: What are the trade-offs between `asyncio.Event`, `asyncio.Condition`, and `asyncio.Queue` for signaling?

**Model answer:**

| Primitive | Use case | Receivers |
|-----------|----------|-----------|
| `asyncio.Event` | Signal "something happened" (no data) | All waiters wake up simultaneously |
| `asyncio.Condition` | Protect shared state + notify | One or all waiters, under a lock |
| `asyncio.Queue` | Pass data between producer/consumer | One consumer gets each item |

```python
# Event: broadcast notification (all waiters wake):
shutdown_event = asyncio.Event()
async def worker():
    await shutdown_event.wait()
    cleanup()
# Setting it wakes ALL workers simultaneously

# Condition: shared-state coordination
condition = asyncio.Condition()
shared_state = []
async def consumer():
    async with condition:
        await condition.wait_for(lambda: len(shared_state) > 0)
        item = shared_state.pop()

async def producer(item):
    async with condition:
        shared_state.append(item)
        condition.notify()  # wake one waiter

# Queue: data handoff (one consumer per item):
queue: asyncio.Queue[int] = asyncio.Queue()
await queue.put(item)
item = await queue.get()  # only one consumer gets it
```

### Q4: How do you integrate asyncio event loops with non-async code or legacy systems?

**Model answer:**

```python
import asyncio

# 1. From sync code: run coroutine to completion
result = asyncio.run(my_async_function())

# 2. Submit work to a running loop from another thread:
loop = asyncio.get_event_loop()  # get the running loop

# From a thread (NOT the loop thread):
future = asyncio.run_coroutine_threadsafe(my_coro(), loop)
result = future.result(timeout=5)  # blocks the calling thread

# 3. call_soon_threadsafe for non-coroutines:
loop.call_soon_threadsafe(queue.put_nowait, event)  # schedule from thread

# 4. Bridge asyncio with a legacy sync callback API:
class LegacyAdapter:
    def __init__(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop
        self._queue: asyncio.Queue = asyncio.Queue()

    def on_message_received(self, msg):
        """Called by legacy system (from unknown thread)."""
        self._loop.call_soon_threadsafe(self._queue.put_nowait, msg)

    async def messages(self):
        """Async generator for the event loop side."""
        while True:
            msg = await self._queue.get()
            if msg is None:
                return
            yield msg
```

### Q5: How do you test event-driven asyncio code reliably?

**Model answer:**

```python
import asyncio
import pytest

@pytest.fixture
def event_loop():
    """Fresh event loop per test."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.mark.asyncio
async def test_event_bus_fanout():
    bus = EventBus()
    q1 = bus.subscribe("test")
    q2 = bus.subscribe("test")

    await bus.publish("test", {"value": 42})

    e1 = await asyncio.wait_for(q1.get(), timeout=1.0)
    e2 = await asyncio.wait_for(q2.get(), timeout=1.0)

    assert e1.payload == {"value": 42}
    assert e2.payload == {"value": 42}

@pytest.mark.asyncio
async def test_backpressure():
    queue: asyncio.Queue = asyncio.Queue(maxsize=2)

    async def slow_consumer():
        await asyncio.sleep(0.1)  # simulate slow processing
        return await queue.get()

    # Fill the queue:
    await queue.put(1)
    await queue.put(2)

    # Third put should block until consumer frees space:
    consumer_task = asyncio.create_task(slow_consumer())
    put_task = asyncio.create_task(queue.put(3))

    await asyncio.gather(consumer_task, put_task)
    assert queue.qsize() == 2
```

---

## Gotcha Follow-ups

**"What happens if you forget to `await` a coroutine in an event handler?"**
The coroutine is never scheduled — it just creates a coroutine object that is immediately garbage collected. Python 3.8+ emits a `RuntimeWarning: coroutine 'X' was never awaited`. In production this is a silent bug: the handler appears to run but does nothing. Solution: always `await` coroutines, use `asyncio.create_task()` to fire-and-forget (but store the task reference to prevent GC).

**"How do you handle exceptions in background tasks without letting them silently swallow?"**
```python
def handle_task_exception(task: asyncio.Task) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        logger.error("Background task failed", exc_info=exc)

task = asyncio.create_task(my_background_coro())
task.add_done_callback(handle_task_exception)
```
Without this, task exceptions are only raised when `.result()` is called. With Python 3.11+ `TaskGroup`, all exceptions are propagated as `ExceptionGroup`.

---

## Under the Hood

asyncio's event loop (`asyncio/base_events.py`) is a `select`/`epoll`/`kqueue` wrapper. Each `await` on an I/O primitive registers a file descriptor with the OS's I/O notification mechanism and suspends the coroutine. When the FD becomes ready, the event loop resumes the coroutine by calling `send(None)` on the generator (since coroutines are syntactic sugar over generators). `asyncio.Queue` is implemented with a `collections.deque` for the internal buffer and `collections.deque` of `asyncio.Future` objects for blocked getters and putters — woken via `future.set_result()` when space/items become available.
