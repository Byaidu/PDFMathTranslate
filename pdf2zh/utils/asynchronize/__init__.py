import asyncio
import time


class Args:
    def __init__(self, args, kwargs):
        self.args = args
        self.kwargs = kwargs


class AsyncCallback:
    MAGIC_MESSAGE_FINISHED = "MAGIC_MESSAGE_FINISHED"

    def __init__(self, timeout=None):
        self.queue = asyncio.Queue()
        self.finished = False
        self.loop = asyncio.get_event_loop()
        self.timeout = timeout

    def step_callback(self, *args, **kwargs):
        # Whenever a step is called, add to the queue but don't set finished to True, so __anext__ will continue
        args = Args(args, kwargs)

        # We have to use the threadsafe call so that it wakes up the event loop, in case it's sleeping:
        # https://stackoverflow.com/a/49912853/2148718
        self.loop.call_soon_threadsafe(self.queue.put_nowait, args)

        # Add a small delay to release the GIL, ensuring the event loop has time to process messages
        time.sleep(0.05)

    def finished_callback(self, *args, **kwargs):
        # Whenever a finished is called, add to the queue as with step, but also set finished to True, so __anext__
        # will terminate after processing the remaining items
        if self.finished:
            return
        self.step_callback(*args, **kwargs)
        self.finished = True

    def finished_callback_without_args(self):
        self.finished_callback(self.MAGIC_MESSAGE_FINISHED)

    def is_finished(self):
        """Return True if the callback has been finished."""
        return self.finished

    def __await__(self):
        # Since this implements __anext__, this can return itself
        return self.queue.get().__await__()

    def __aiter__(self):
        # Since this implements __anext__, this can return itself
        return self

    async def __anext__(self):
        # Keep waiting for the queue if a) we haven't finished, or b) if the queue is still full. This lets us finish
        # processing the remaining items even after we've finished
        if self.finished and self.queue.empty():
            raise StopAsyncIteration

        if isinstance(self.timeout, int) or isinstance(self.timeout, float):
            result = await asyncio.wait_for(self.queue.get(), self.timeout)
        else:
            result = await self.queue.get()
        if result.args[0] == self.MAGIC_MESSAGE_FINISHED:
            raise StopAsyncIteration
        return result
