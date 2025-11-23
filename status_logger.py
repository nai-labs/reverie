import sys
from colorama import init, Fore, Style

# Initialize colorama
init()

class StatusLogger:
    """
    Handles unified status updates for both the terminal and the launcher GUI.
    Emits colored messages to stdout with a specific prefix that the launcher can parse.
    """
    
    PREFIX = "[STATUS]"
    status_file = None

    @staticmethod
    def set_status_file(path):
        """Sets the path for the status file."""
        StatusLogger.status_file = path

    @staticmethod
    def print_status(message, color=Fore.WHITE):
        """
        Prints a formatted status message to stdout and writes to status file.
        
        Args:
            message (str): The status message to display.
            color (str): The color to use for the message (from colorama.Fore).
        """
        # Format: [STATUS] Message content
        # The launcher will look for the [STATUS] prefix
        print(f"{StatusLogger.PREFIX} {color}{message}{Style.RESET_ALL}")
        sys.stdout.flush() # Ensure it's sent immediately
        
        # Write to status file if set
        if StatusLogger.status_file:
            try:
                with open(StatusLogger.status_file, "w") as f:
                    f.write(message)
            except Exception:
                pass # Ignore file errors to prevent crashing the bot

    @staticmethod
    def print_success(message):
        """Prints a success message in green."""
        StatusLogger.print_status(message, Fore.GREEN)

    @staticmethod
    def print_error(message):
        """Prints an error message in red."""
        StatusLogger.print_status(message, Fore.RED)

    @staticmethod
    def print_info(message):
        """Prints an info message in cyan."""
        StatusLogger.print_status(message, Fore.CYAN)

    @staticmethod
    def print_warning(message):
        """Prints a warning message in yellow."""
        StatusLogger.print_status(message, Fore.YELLOW)
