import os
import sh
import json

from tails_server import util
from tails_server.config import ANSIBLE_PLAYBOOK_DIR

# XXX: Use an existing solution to modify config files, e.g. Ansible


def ansible_add_hs_to_torrc(service_name, content):
    playbook = os.path.join(ANSIBLE_PLAYBOOK_DIR, "add_hs.yml")
    extra_vars = {"service_name": service_name, "content": content}
    sh.ansible_playbook(playbook, "--extra-vars", json.dumps(extra_vars))


def ansible_remove_hs_from_torrc(service_name):
    playbook = os.path.join(ANSIBLE_PLAYBOOK_DIR, "remove_hs.yml")
    extra_vars = {"service_name": service_name}
    sh.ansible_playbook(playbook, "--extra-vars", json.dumps(extra_vars))


def append_to_file(file_path, s):
    with util.open_locked(file_path, 'a') as f:
        f.write(s)


def prepend_to_file(file_path, s):
    with util.open_locked(file_path, 'r') as original:
        original_content = original.read()
    with util.open_locked(file_path, 'w') as f:
        f.write(s + original_content)


def append_line_if_not_present(file_path, line_):
    with util.open_locked(file_path, 'r+') as f:
        if line_ in f.readlines():
            return False
        f.write(line_)
        return True


def remove_line_if_present(file_path, line_):
    removed = False
    with util.open_locked(file_path, 'r') as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        if line == line_:
            del lines[i]
            removed = True
    with util.open_locked(file_path, 'w+') as f:
        f.writelines(lines)
    return removed


def delete_lines_starting_with(file_path, s):
    with util.open_locked(file_path, 'r') as f:
        lines = f.readlines()
    lines = [line for line in lines if not line.startswith(s)]
    with util.open_locked(file_path, 'w+') as f:
        f.writelines(lines)


def insert_to_section(file_path, section_name, s):
    def write_to_file():
        with util.open_locked(file_path, 'w+') as f:
            f.writelines(lines)

    with util.open_locked(file_path, 'r') as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        if line.startswith("[%s]" % section_name):
            lines.insert(i+1, s)
            write_to_file()
            return

    lines.append("[%s]" % section_name)
    lines.append(s)
    write_to_file()


def delete_section(file_path, section_name):
    def get_lines_of_section(lines, offset):
        i = 0
        for line in lines[offset+1:]:        
            if line.startswith("["):
                break
            i += 1
        return list(range(offset, offset+i+1))

    with util.open_locked(file_path, 'r') as f:
        lines = f.readlines()
    
    lines_to_delete = list()

    for i, line in enumerate(lines):
        if line.startswith("[%s]" % section_name):
            lines_to_delete += get_lines_of_section(lines, i)

    lines = [line for i, line in enumerate(lines) if i not in lines_to_delete]

    with util.open_locked(file_path, 'w+') as f:
        f.writelines(lines)


def find_line_starting_with(file_path, s):
    with util.open_locked(file_path, 'r') as f:
        lines = f.readlines()
    for line in lines:
        if line.startswith(s):
            return line
