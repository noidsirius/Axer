import logging
import sys
from pathlib import Path
from typing import Union

BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)


#The background is set with 40 plus the number of the color, and the foreground with 30


#These are the sequences need to get colored ouput
RESET_SEQ = "\033[0m"
COLOR_SEQ = "\033[0;%dm"
BOLD_COLOR_SEQ = "\033[1;%dm"
BOLD_SEQ = "\033[1m"


def fix_formatter(logger_format: str, use_color=True):
    if use_color:
        logger_format = logger_format.replace("$RESET", RESET_SEQ).replace("$BOLD", BOLD_SEQ)
    else:
        logger_format = logger_format.replace("$RESET", "").replace("$BOLD", "")
    return logger_format


COLORS = {
    'WARNING': YELLOW,
    'INFO': CYAN,
    'DEBUG': BLUE,
    'CRITICAL': YELLOW,
    'ERROR': RED
}


def colorize(message: str, color: int = WHITE, bold: bool = False) -> str:
    color_seq = BOLD_COLOR_SEQ if bold else COLOR_SEQ
    return color_seq % (30+color) + message + RESET_SEQ


DETAILED_LOGGER_FORMAT = f'%(module)-25s - %(funcName)-30s %(asctime)s.%(msecs)03d %(levelname)-20s: %(message)s'
SIMPLE_LOGGER_FORMAT = f'%(levelname)20s: %(message)s'
LOGGER_DATE_FORMAT = f'%m-%d {colorize("%H:%M:%S", bold=True)}'


class ColoredFormatter(logging.Formatter):
    def __init__(self, detailed: bool = False, use_color=True):
        logger_format = fix_formatter(DETAILED_LOGGER_FORMAT if detailed else SIMPLE_LOGGER_FORMAT, use_color=use_color)
        logging.Formatter.__init__(self, logger_format, LOGGER_DATE_FORMAT)
        self.use_color = use_color

    def format(self, record):
        levelname = record.levelname
        if self.use_color and levelname in COLORS:
            record.levelname = colorize(levelname, COLORS[levelname], levelname == 'ERROR')
        return logging.Formatter.format(self, record)


def initialize_logger(log_path: Union[str, Path], quiet: bool = False, debug: bool = True):
    if debug:
        level = logging.DEBUG
    else:
        level = logging.INFO

    logger_handlers = [logging.FileHandler(log_path, mode='w')]
    logger_handlers[0].setFormatter(ColoredFormatter(detailed=True, use_color=True))
    if not quiet:
        logger_handlers.append(logging.StreamHandler())
        logger_handlers[-1].setFormatter(ColoredFormatter(detailed=False, use_color=True))
    logging.basicConfig(handlers=logger_handlers)
    # ---------------- Start Hack -----------
    py_src_path = Path(str(Path(sys.argv[0]).resolve()).split('py_src')[0]).joinpath("py_src")
    py_src_file_names = [p.name[:-len(".py")] for p in py_src_path.rglob('*.py')]
    for name in logging.root.manager.loggerDict:
        if name.split('.')[-1] in py_src_file_names or name == "__main__":
            logging.getLogger(name).setLevel(level)
    # ----------------- End Hack ------------
