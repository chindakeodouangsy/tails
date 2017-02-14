import os

from tails_server import option_template
from tails_server import file_util

# XXX: Use an existing solution to parse config files


def get_option(file_path, s):
    if not os.path.exists(file_path):
        raise option_template.OptionNotFoundError("File %r not found" % file_path)

    line = file_util.find_line_starting_with(file_path, s)

    if not line:
        raise option_template.OptionNotFoundError(
            "Could not find line starting with %r in file %r" % (s, file_path))
    return line.replace(s, "").rstrip()
