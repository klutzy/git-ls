#!/usr/bin/env python

import subprocess
import os.path


def c(msg, color=None, bold=False, bgcolor=None):
    colors = []
    if bold:
        colors.append(1)
    if color:
        colors.append(color)
    if bgcolor:
        colors.append(bgcolor)

    if not colors:
        return msg

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


def git_ls_tree(path, tree="HEAD"):
    ret = []

    path = os.path.normpath(path) + "/"
    output = git("ls-tree", "--full-name", tree, path)
    for line in output.splitlines():
        tmp, file_name = line.split("\t", 1)
        file_mode, file_type, file_obj = tmp.split(" ")
        # TODO file_size?
        ret.append((file_mode, file_type, file_obj, file_name))

    return ret


def output_line(x, y, path, path_to=None, path_from=None,
                with_untracked=False):
    output = path
    extra = ""

    if path_to:
        output = "{path} -> {path_to}".format(path=path, path_to=path_to)
    elif path_from:
        output = "{path} <- {path_from}".format(path=path,
                                                path_from=path_from)

    if with_untracked:
        extra += c("*", bold=True)

    # TODO use `git config color.status.???`
    color = 0
    bold = False
    if (x, y) == ("?", "?"):
        color = 31
    else:
        if x and y:
            color = 35
        elif x:
            color = 32
        elif y:
            color = 31
    output = c(output, color, bold=bold)
    template = "{x}{y}\t{output}{extra}"
    if not x:
        x = ' '
    if not y:
        y = ' '
    return template.format(x=x, y=y, output=output, extra=extra)


def main():
    if git("rev-parse", "--is-inside-work-tree").strip() == "false":
        print("not inside working directory")
        return

    prefix = git("rev-parse", "--show-prefix").strip()  # can be ""

    status = git_status()
    ls_tree = git_ls_tree(prefix)

    done = []

    # print working tree status
    for file_mod, file_type, file_obj, file_name in ls_tree:
        x, y, path_from, path_to = '', '', None, None
        with_untracked = False
        if file_type == 'blob':
            file_status = [i for i in status if file_name in i[2:]]
            # len(file_status) can be >1 e.g. `git rm file --cached`
            for info in file_status:
                x, y, pf, pt = info
                if (x, y) == ("?", "?"):
                    with_untracked = True
                elif pt == file_name:
                    path_from = pf
                elif pf == file_name:
                    path_to = pt
        print output_line(x, y, file_name, path_from=path_from,
                          path_to=path_to, with_untracked=with_untracked)
        done.append(file_name)

    # print new and untracked files
    for x, y, file_name, _ in status:
        if file_name in done:
            continue
        print output_line(x, y, file_name)
        done.append(file_name)


if __name__ == '__main__':
    main()
