#!/usr/bin/env python

import argparse
import os
import os.path
import stat
import subprocess
import sys


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


def gits(*args):
    # like git() but silently
    try:
        devnull = open(os.devnull, 'w')
        return subprocess.check_output(["git"] + list(args), stderr=devnull)
    except subprocess.CalledProcessError:
        return ""


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
    output = gits("ls-tree", "--full-name", tree, path)
    for line in output.splitlines():
        tmp, file_name = line.split("\t", 1)
        file_mode, file_type, file_obj = tmp.split(" ")
        # TODO file_size?
        ret.append((file_mode, file_type, file_obj, file_name))

    return ret


def git_submodules(fn):
    ret = {}
    if not os.path.isfile(fn):
        return ret

    path = None
    url = None
    for line in file(fn, 'r').readlines():
        if line.startswith("["):
            ret[path] = url
            path = None
            url = None
        elif line.startswith("\tpath"):
            path = line.split("=", 1)[1].strip()
        elif line.startswith("\turl"):
            url = line.split("=", 1)[1].strip()
    if path:
        ret[path] = url
    return ret


def get_file_mode(git_mode, cur_mode):
    ret = ''

    if cur_mode is None:
        cur_mode = 0

    def s(flag, flag_char, ignore_git=False):
        ret = '-'
        git_flag = None
        cur_flag = None
        if cur_mode:
            cur_flag = cur_mode & flag
            ret = flag_char if cur_flag else '-'
            if git_mode is not None:
                git_flag = git_mode & flag
                if not ignore_git and bool(git_flag) != bool(cur_flag):
                    ret = c(ret, 31, bold=True)
        return ret

    file_type = '-'
    if git_mode == 0160000:
        # gitlink e.g. submodule
        file_type = 'g'
    elif stat.S_ISSOCK(cur_mode):
        file_type = 's'
    elif stat.S_ISLNK(cur_mode):
        file_type = 'l'
    elif stat.S_ISBLK(cur_mode):
        file_type = 'b'
    elif stat.S_ISCHR(cur_mode):
        file_type = 'c'
    elif stat.S_ISFIFO(cur_mode):
        file_type = 'p'
    elif stat.S_ISDIR(cur_mode):
        file_type = 'd'

    ret += file_type

    for target in ('USR', 'GRP', 'OTH'):
        for mode in 'RWX':
            flag = getattr(stat, 'S_I{}{}'.format(mode, target))
            ret += s(flag, mode.lower(), ignore_git=(file_type != '-'))

    return ret


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument('path', default='.', nargs='?')
    args = argparser.parse_args()
    try:
        os.chdir(args.path)
    except OSError as e:
        sys.stderr.write(str(e) + "\n")
        return

    prefix = ""
    status = {}
    ls_tree_dic = {}
    ls_tree_files = []
    submodules = {}
    if gits("rev-parse", "--is-inside-work-tree").strip() == "true":
        prefix = git("rev-parse", "--show-prefix").strip()  # can be ""

        status = git_status()
        ls_tree = git_ls_tree('.')
        for fm, ft, fo, fn in ls_tree:
            ls_tree_files.append(fn)
            ls_tree_dic[fn] = (fm, ft, fo)

        toplevel = git("rev-parse", "--show-toplevel").strip()
        submodules = git_submodules(os.path.join(toplevel, ".gitmodules"))

    files = []
    directories = []

    # print working tree status
    output_lines = []
    local_files = [os.path.normpath(os.path.join(prefix, i))
                   for i in os.listdir('.')]
    for file_name in ls_tree_files + local_files:
        file_path = os.path.relpath(file_name, prefix)
        is_directory = os.path.isdir(file_path)
        x, y, path_from, path_to = '', '', None, None
        with_untracked = False
        submodule = False
        if not is_directory:
            if file_name in files:
                continue
            file_status = [i for i in status if file_name in i[2:]]
            # len(file_status) can be >1 e.g. `git rm file --cached`
            if not file_status and not file_name in ls_tree_dic:
                # ignored file
                if not ls_tree_dic:
                    # maybe the whole directory is untracked
                    # it may be better to print all files
                    x, y = "?", "?"
                else:
                    continue
            for info in file_status:
                x, y, pf, pt = info
                if (x, y) == ("?", "?"):
                    with_untracked = True
                elif pt == file_name:
                    path_from = pf
                elif pf == file_name:
                    path_to = pt
            files.append(file_name)
            if path_from:
                files.append(path_from)
            if path_to:
                files.append(path_to)
        else:
            # summarize subdirectory changes
            if file_name in directories:
                continue

            def is_subdir(path):
                if path == file_name:
                    return True
                if path and path.startswith(file_name + "/"):
                    return True
                return False

            subdir_status = [i for i in status if
                             is_subdir(i[2]) or is_subdir(i[3])]
            if not subdir_status and not file_name in ls_tree_dic:
                # untracked directory
                if not ls_tree_dic:
                    x, y = "?", "?"
                else:
                    continue
            for info in subdir_status:
                if info[:2] == ("?", "?"):
                    with_untracked = True
                else:
                    x = info[0] if not x else x if x == info[0] else "*"
                    y = info[1] if not y else y if y == info[0] else "*"

                files.append(info[2])
            directories.append(file_name)

        if file_name in submodules:
            submodule = submodules[file_name]

        # relative file names
        file_name = os.path.relpath(file_name, prefix)
        if path_from:
            path_from = os.path.relpath(path_from, prefix)
        if path_to:
            path_to = os.path.relpath(path_to, prefix)

        output = file_name
        extra = ""

        # generate output_line
        if path_to:
            output = "{path} -> {path_to}".format(path=file_name,
                                                  path_to=path_to)
        elif path_from:
            output = "{path} <- {path_from}".format(path=file_name,
                                                    path_from=path_from)

        if with_untracked:
            extra += c("*", bold=True)
        if submodule:
            extra += " @ {submodule}".format(submodule=c(submodule, color=32))

        # TODO use `git config color.status.???`
        # print order: staged, staged+unstaged, unstaged, uneditted, untracked
        color = 0
        priority = 0
        if (x, y) == ("?", "?"):
            color = 31
            priority = -1
        else:
            if x and y:
                color = 35
                priority = 2
            elif x:
                color = 32
                priority = 3
            elif y:
                color = 31
                priority = 1

        git_file_mode = None
        if file_name in ls_tree_dic:
            git_file_mode, _, _ = ls_tree_dic[file_name]
            git_file_mode = int(git_file_mode, 8)
        current_file_mode = None
        try:
            current_file_mode = os.lstat(file_name).st_mode
        except OSError:
            pass
        file_mode = get_file_mode(git_file_mode, current_file_mode)

        output = c(output, color, bold=is_directory)
        template = "{file_mode} {x}{y} {output}{extra}"
        if not x:
            x = ' '
        if not y:
            y = ' '
        output_line = template.format(file_mode=file_mode, x=x, y=y,
                                      output=output, extra=extra)

        sort_key = (-int(is_directory), -priority, file_name)
        output_lines.append((sort_key, output_line))

    output_lines.sort()
    for i in output_lines:
        print i[-1]

if __name__ == '__main__':
    main()
