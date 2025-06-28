import logging
import sys


def setup_logging(
    name: str = "app",
    level: str = "INFO",
    show_module: bool = True,
    show_function: bool = False,
):
    """
    Set up console-only logging configuration with colors.

    Args:
        name: Logger name (usually __name__ or app name)
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        show_module: Whether to show module name in logs
        show_function: Whether to show function name in logs

    Returns:
        Configured logger instance
    """

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # Clear any existing handlers
    logger.handlers.clear()

    # Build format string based on options
    format_parts = ["%(asctime)s", "%(levelname)-8s"]

    if show_module:
        format_parts.append("%(name)s:%(lineno)d")
    if show_function:
        format_parts.append("%(funcName)s()")

    format_parts.append("%(message)s")
    format_string = " | ".join(format_parts)

    # Colored formatter for console output
    class ColorFormatter(logging.Formatter):
        """Colored formatter for console output"""

        COLORS = {
            "DEBUG": "\033[36m",  # Cyan
            "INFO": "\033[32m",  # Green
            "WARNING": "\033[33m",  # Yellow
            "ERROR": "\033[31m",  # Red
            "CRITICAL": "\033[35m",  # Magenta
            "RESET": "\033[0m",  # Reset
        }

        def format(self, record):
            color = self.COLORS.get(record.levelname, "")
            reset = self.COLORS["RESET"]
            record.levelname = f"{color}{record.levelname}{reset}"
            return super().format(record)

    formatter = ColorFormatter(fmt=format_string, datefmt="%Y-%m-%d %H:%M:%S")

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


# Convenience function for quick setup
def get_logger(name: str = None, level: str = "INFO"):
    """Quick logger setup with sensible defaults"""
    if name is None:
        name = "noname"

    return setup_logging(name=name, level=level, show_module=True, show_function=True)
