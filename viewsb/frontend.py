"""
ViewSB frontend class definitions -- defines the abstract base for things that display USB data
"""

import io
import sys
import queue

from .ipc import ProcessManager

class ViewSBEnumerableFromUI:
    """ Mix-in for classes that are intended to have their subclasses enumerated from the UI.

    Used primarily for the frontends, backends, and filters.
    """

    # Each subclass should override this class variable with their preferred name.
    UI_NAME = None
    UI_DESCRIPTION = None

    @classmethod
    def available_on_system(cls):
        """ Returns true iff this class can be used on the current system.

        Generally, prefer implementing reason_for_disabling, and allowing this
        function to automatically determine using its result.
        """
        return (cls.reason_to_be_disabled() is None)


    @classmethod
    def reason_to_be_disabled(cls):
        """
        Returns a string describing any reasons this class would be unavailable, or None
        if the backend is currently available.

        The latter condition is mandatory for implementers; it will be used by the default
        implementation of `available_for_capture`.
        """
        # Assume by default the given decoder is always enabled.
        return None


    @staticmethod
    def parse_arguments(args, parent_parser=[]):
        """ Optional method that parses command-line options with which to set up the given module.

        Typically, this would be used by instantiating your own argparse instance and consuming from
        the remaining arguments.

        Returns: parsed_args, leftover_args
            parsed_args -- a tuple of arguments that should be passed to the class constructor
            leftover_args -- A list of any arguments left over after parsing.
        """
        return ((), args)


    @classmethod
    def get_subclass_from_name(cls, name):
        """ Attempts to look up a subclass by its UI_NAME.

        Returns a subclass if one was found; or None if nothing matched the UI_NAME.
        """

        for subclass in cls.all_named_subclasses():
            if subclass.UI_NAME == name:
                return subclass

        return None



    @classmethod
    def all_named_subclasses(cls):
        """ Returns the set of all subclasses of the relevant class that have a UI_NAME defined.

        Args:
            include_self -- True iff we want to consider 'self' a subclass of the current class.
        """

        subclasses = set()

        # Search each of our subclasses...
        for subclass in cls.__subclasses__():
            # If the current class is named, add it to our list...
            if subclass.UI_NAME:
                subclasses.add(subclass)

            # ... and explore all of its subclasses.
            subclasses.update(subclass.all_named_subclasses())

        return subclasses




    @classmethod
    def available_subclasses(cls):
        """ Returns an iterator over all available backend objects. """
        return (subclass for subclass in cls.all_named_subclasses() if subclass.available_on_system())


    @classmethod
    def unavailable_subclasses(cls):
        """
        Returns a generator of 2-tuples for each unavailable backend, in the following format:

        (backend, reason), where:
            backend -- The unavailable backend class.
            reason -- The reason the given backend isn't available.
        """
        unavailable = []

        return ((subclass, subclass.reason_to_be_disabled()) \
            for subclass in cls.all_named_subclasses() if not subclass.available_on_system())



class ViewSBFrontendProcess(ProcessManager):
    """ Class that controls and communicates with a ViewSB UI running in another process. """
    pass




class ViewSBFrontend(ViewSBEnumerableFromUI):
    """ Generic parent class for sources that display USB data. """

    # Frontend information for any UIs that want to display it.
    # Should be overridden by the relevant class.
    UI_NAME        = None
    UI_DESCRIPTION = None

    PACKET_READ_TIMEOUT = 0.01

    def __init__(self):
        """
        Function that initializes the relevant frontend. In most cases, this objects won't be instantiated
        directly -- but instead instantiated by the `run_asynchronously` / 'run_frontend_asynchronously` helpers.
        """
        pass


    def set_up_ipc(self, data_queue, termination_event, stdin=None):
        """
        Function that accepts the synchronization objects we'll use for input. Must be called prior to
        calling run().

        Args:
            data_queue -- The Queue object that will feed up analyzed packets for display.
            termination_event -- A synchronization event that is set when a capture is terminated.
        """

        # Store our IPC primitives, ready for future use.
        self.data_queue        = data_queue
        self.termination_event = termination_event

        # Retrieve our use of the standard input from the parent thread.
        if stdin:
            self.stdin = sys.stdin = stdin



    def read_packet(self, blocking=True, timeout=None):
        """ Reads a packet from the analyzer process.

        Args:
            blocking -- If set, the read will block until a packet is available.
            timeout -- The longest time to wait on a blocking read, in floating-point seconds.
        """
        return self.data_queue.get(blocking, timeout=timeout)


    def handle_events(self):
        pass


    def handle_incoming_packet(self, packet):
        pass


    def fetch_packet_from_analyzer(self):
        """
        Fetch any packets the analyzer has to offer. Blocks for a short period if no packets are available,
        to minimize CPU busy-waiting.
        """

        try:
            # Read a packet from the backend, and add it to our analysis queue.
            return self.read_packet(timeout=self.PACKET_READ_TIMEOUT, blocking=False)

        except queue.Empty:
            # If no packets were available, return without error; we'll wait again next time.
            return None


    def handle_communications(self):
        """
        Function that handles communications with our analyzer process.
        Should be called repeatedly during periods when the UI thread is not busy;
        if you override run(). it's your responsibility to call this function.
        """

        packet = True

        while packet:

            # Try to fetch a packet from the analyzer.
            packet = self.fetch_packet_from_analyzer()

            # If we got one, handle using it in our UI.
            if not packet:
                break

            self.handle_incoming_packet(packet)


    def run(self):
        """ Runs the given frontend until either side requests termination. """

        # Capture infinitely until our termination signal is set.
        while not self.termination_event.is_set():
            self.handle_communications()

        # Allow the subclass to handle any cleanup it needs to do.
        self.handle_termination()


    def handle_termination(self):
        """ Called once the capture is terminated; gives the frontend the ability to clean up. """
        pass

