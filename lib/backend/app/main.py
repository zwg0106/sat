"""main class."""
import os
import sys
import asyncio
import signal
from concurrent.futures import ThreadPoolExecutor
from logger import LOGGER
from web_server import SatWebServer
import concurrent.futures
from threading import Thread
from asyncio import coroutines
from asyncio.futures import Future

def __signal_handler(signal, frame):
    """Callback for CTRL-C."""
    end()


def end():
    """Stop Sat."""
    LOGGER.info("Sat stopped (keypressed: CTRL-C)")

    # The end...
    sys.exit(0)

def attempt_use_uvloop() -> None:
	"""Attempt to use uvloop."""
	import asyncio

	try:
		import uvloop
		asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
	except ImportError:
		pass

def async_loop_exception_handler(loop, context):
    """Handle all exception inside the loop."""
    kwargs = {} 
    exception = context.get('exception')
    if exception:
        kwargs['exc_info'] = (type(exception), exception,
                              exception.__traceback__)

    LOGGER.error(  # type: ignore
        "Error doing job: %s", context['message'], **kwargs)


class Core(object):
    """ Core object """
    def __init__(self):
        self.loop = asyncio.get_event_loop()

        executor_opts = {'max_workers': None}
        if sys.version_info[:2] >= (3, 6):
            executor_opts['thread_name_prefix'] = 'SyncWorker'

        self.executor = ThreadPoolExecutor(**executor_opts)
        self.loop.set_default_executor(self.executor)
        self.loop.set_exception_handler(async_loop_exception_handler)

        if asyncio.get_child_watcher()._loop is not self.loop:
            asyncio.get_child_watcher().attach_loop(self.loop)

   
    def run_loop(self):
        self.loop.run_forever()


    def start(self):
        # Run forever
        try:
            #block until stopped
            LOGGER.info("Starting sat core loop")
            Thread(target=self.run_loop, daemon=True).start()
        finally:
            pass 

    # no return value checking
    def add_task(self, target, *args):
        """ Add task into executor pool 
        this method must be run in event loop
        """

        if target is None:
            raise ValueError("Don't call add_task with None")
        self.loop.call_soon_threadsafe(self.async_add_task, target, *args)


    def async_add_task(self, target, *args):
        task = None

        if asyncio.iscoroutine(target):
            task = self.loop.create_task(target)
        elif asyncio.iscoroutinefunction(target):
            task = self.loop.create_task(target(*args))
        else:
            task = self.loop.run_in_executor(None, target, *args)

        return task


    # checking return value for callback running with threadsafe
    def run_callback_threadsafe(self, callback, *args, **kargs):
        """ Submit a callback object to a given event loop.
        Return a concurrent.futures.Future to access the result.
        this method must be run in event loop
        """

        future = concurrent.futures.Future()

        def run_callback():
            """ Run callback and store result."""
            try:
                LOGGER.info(args)
                LOGGER.info(kargs)
                future.set_result(callback(*args, **kargs))
            except Exception as exc:
                if future.set_running_or_notify_cancel():
                    future.set_exception(exc)
                else:
                    LOGGER.error("Exception on lost future: ", exc_info=True)
        
        self.loop.call_soon_threadsafe(run_callback)
        return future


    # checking return value for coroutinue running with threadsafe
    def run_coroutine_threadsafe(self, coro, *args, **kargs):
        """ Submit a coroutine object to a given event loop.
        Return a concurrent.futures.Future to access the result.
        this method must be run in event loop
        """
        
        if not coroutines.iscoroutinefunction(coro):
            raise TypeError('A coroutine function is required')

        future = concurrent.futures.Future()

        #Future is asyncio.futures.Future
        def got_result(task):
            exception = task.exception()
            if exception is not None:
                future.set_exception(exception)
            else:
                future.set_result(task.result())

        def run_callback():
            """Run callback and store result."""
            try:
                task = asyncio.ensure_future(coro(*args, **kargs), loop=self.loop)
                task.add_done_callback(got_result)
            except Exception as exc:
                if future.set_running_or_notify_cancel():
                    future.set_exception(exc)
                else:
                    LOGGER.warning("Exception on lost future: ", exc_info=True)

        self.loop.call_soon_threadsafe(run_callback)
        return future


    async def run_async_shell_command(self, cmd, output=None):
        """ execute shell command 
        support: cmd = 'ls -l' or cmd = ['ls', '-l']
        this method must be run in event loop
        """
        if ' ' not in cmd:
            prog = cmd
            args = None
        else:
            prog, args = cmd.split(' ', 1)

        if output is None:
            out = asyncio.subprocess.PIPE
        else:
            out = output

        if args:
            create_process = asyncio.create_subprocess_shell(
                            cmd,
                            loop=self.loop,
                            stdin=None,
                            stdout=out,
                            stderr=asyncio.subprocess.PIPE,)
           

        else:
            create_process = asyncio.create_subprocess_exec(
                            *cmd,
                            loop=self.loop,
                            stdin=None,
                            stdout=out,
                            stderr=asyncio.subprocess.PIPE,)

        process = await create_process
        stdout_data, stderr_data = await process.communicate()

        if output is None and stdout_data:
            pass
            #LOGGER.debug("Stdout of command: '%s', return code: %s:\n%s",
            #            cmd, process.returncode, stdout_data)
        if stderr_data:
            #LOGGER.debug("Stderr of command: '%s', return code: %s:\n%s",
            #            cmd, process.returncode, stderr_data)
            pass

        if process.returncode != 0:
            LOGGER.error("Error running command: '%s', return code: %s",
                        cmd, process.returncode)

        if output:
            return stderr_data
        else:
            return stdout_data, stderr_data


class SatMain(object):
    def __init__(self):
        """ Init new SAT object """
        self.core = Core()
        
        # Init web server
        self.web_app = SatWebServer(self.core)

    def start(self):
        self.core.start()
        
        """ start web server and core """
        self.web_app.start()


def start():
    """ Main entry point for sat """

    # Catch the CTRL-C signal
    signal.signal(signal.SIGINT, __signal_handler)

    attempt_use_uvloop()

    # Share global sat instance
    #global sat 

    # Create the SAT main instance
    sat = SatMain()

    sat.start()


if __name__ == "__main__":
    start()

