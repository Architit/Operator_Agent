import logging

from agent.logger import get_logger, set_level


def test_get_logger_does_not_duplicate_handlers():
    logger = get_logger("operator.test.logger")
    before = len(logger.handlers)
    logger_again = get_logger("operator.test.logger")
    after = len(logger_again.handlers)
    assert after == before


def test_set_level_updates_logger_level():
    logger = get_logger("operator.test.level")
    set_level("DEBUG")
    assert logger.level == logging.DEBUG
    set_level("INFO")
