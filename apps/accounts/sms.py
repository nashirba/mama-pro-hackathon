import logging

logger = logging.getLogger(__name__)


class ConsoleSmsSender:
    """Demo SMS sender: writes the message to the log instead of sending it."""

    def send(self, phone: str, text: str) -> None:
        logger.info("SMS to %s: %s", phone, text)


def get_sms_sender() -> ConsoleSmsSender:
    return ConsoleSmsSender()
