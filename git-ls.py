#!/usr/bin/env python

import subprocess
import os.path


def c(msg, colors):
    color = ';'.join(str(i) for i in colors)
    return "\033[{color}m{msg}\033[0m".format(msg=msg, color=color)


def git(*args):
    return subprocess.check_output(["git"] + list(args))


def git_status():
    ret = []

    output = git("status", "--porcelain")
    for line in output.splitlines():
        x = line[0].strip()
        y = line[1].strip()
        path = line[3:]
        path_to = None

        if " -> " in path:
            # XXX not exact: ".bash -> rc" -> .bashrc
            path, path_to = path.split(" -> ", 1)
        ret.append((x, y, path, path_to))

    return ret


def output_line(x, y, path, path_to):
    output = path
    extra = ""

    if path_to:
        output = "{path} -> {path_to}".format(path=path, path_to=path_to)

    # TODO use `git config color.status.???`
    # TODO bold directories
    color = 0
    if (x, y) == ("?", "?"):
        color = 31
    else:
        if x and y:
            color = 35
        elif x:
            color = 32
        elif y:
            color = 31
    if color:
        output = c(output, [color])
    template = "{x}{y}\t{output}{extra}"
    return template.format(x=x, y=y, output=output, extra=extra)


def main():
    if git("rev-parse", "--is-inside-work-tree").strip() == "false":
        print("not inside working directory")
        return

    for x, y, path, path_to in git_status():
        print output_line(x, y, path, path_to)
    pass


if __name__ == '__main__':
    main()
