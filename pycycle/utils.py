import ast
import codecs
import logging
import os
import re
import sys
import traceback
from collections import defaultdict
from typing import Dict, List, Optional, Iterable

import click
import crayons

if sys.version_info[0] > 2:
    open_func = open
else:
    open_func = codecs.open

REGEX_RELATIVE_PATTERN = re.compile('from \\.')

# logger
_LOGGER = logging.getLogger(__name__)


class Node(object):
    """The class represents info about one project module"""

    def __init__(self, name, imports=None, full_path=None, line_no=None):
        self.name = name
        if not imports:
            self.imports = []
        else:
            self.imports = imports

        self.is_imported_from = defaultdict(list)
        self.full_path = full_path
        self.marked = 0
        self.parent = None
        self.func_imports = {}
        self.func_defs = {}
        self.is_in_context = False

    def __iter__(self):
        return iter(self.imports)

    def add(self, item: 'Node'):
        self.imports.append(item)

    def __repr__(self):
        return self.name + ':' + str(len(self.imports))

    def is_imported_from_any(self, nodes: List['Node']) -> bool:
        """:return: whether the node is imported by any node from the given list"""
        for node in nodes:
            if self.is_imported_from[node.full_path]:
                return True
        return False


def _add_new_node(root_path: str, name: str, lineno: int, nodes: Dict[str, Node], node: Node, full_path: str) -> bool:
    """Adds new node into list of nodes.

    :param root_path: absolute path to the module
    :param name: of the imported module
    :param lineno: line number, where the import was found
    :param nodes: already imported nodas
    :param node:
    :param full_path: full path to parent node, that imported new node
    :return: True if new node added; False ownerwise
    """
    path_to_module = get_path_from_package_name(root_path, name)

    if path_to_module in nodes:
        new_node = nodes[path_to_module]
    elif os.path.isfile(path_to_module):
        new_node = Node(name, full_path=path_to_module)
        nodes[path_to_module] = new_node
    else:
        new_node = None

    if new_node:
        new_node.is_imported_from[full_path].append(lineno)
        node.add(new_node)
        return True
    return False


def _add_missing_module(missing_modules: List[str], root_path: str, name: str) -> None:
    """Updates missing modules with additional imported module.

    :param missing_modules: list of missing modules
    :param root_path: to the imported module
    :param name: of the missing module being imported
    """
    path_to_module = get_path_from_package_name(root_path, name)
    if path_to_module not in missing_modules:
        missing_modules.append(path_to_module)
        _LOGGER.debug('Imported module not found: ' + path_to_module)


def read_project(root_path: str, verbose: bool = False, ignore: Optional[List[str]] = None, encoding: Optional[str] = None) -> List[Node]:
    """
    Reads project into an AST and transforms imports into Nodes
    :param root_path: String
    :param verbose: TBD
    :param ignore: TBD
    :param: encoding: TBD
    :return: list of nodes found during parsing
    """
    nodes = {}  # Dict[str, Node]
    root_node = None
    errors = False
    ignore_files = set([".hg", ".svn", ".git", ".tox", "__pycache__", "env", "venv"]) # python 2.6 comp
    missing_modules = []

    if ignore:
        for ignored_file in ignore:
            ignore_files.add(os.path.basename(os.path.realpath(ignored_file)))

    # traverse root directory, and list directories as dirs and files as files
    for root, dirs, files in os.walk(root_path):

        dirs[:] = [d for d in dirs if d not in ignore_files]

        files = [fn for fn in files if os.path.splitext(fn)[1] == ".py" and fn not in ignore_files]

        for file_name in files:
            full_path = os.path.join(root, file_name)
            with open_func(full_path, "r", encoding=encoding) as f:
                try:
                    # fails on empty files
                    file_data = f.read()
                    lines = file_data.splitlines()
                    tree = ast.parse(file_data)
                    if verbose:
                        click.echo(crayons.yellow('Trying to parse file: {}'.format(full_path)))

                    if full_path in nodes:
                        node = nodes[full_path]
                    else:
                        node = Node(file_name[:-3], full_path=full_path)
                        nodes[full_path] = node

                    if not root_node:
                        root_node = node

                    for ast_node in ast.walk(tree):
                        if isinstance(ast_node, ast.Import) and ast_node.names:
                            for subnode in ast_node.names:
                                if not subnode.name:
                                    continue
                                if not _add_new_node(root_path, subnode.name, ast_node.lineno, nodes, node, full_path):
                                    _add_missing_module(missing_modules, root_path, subnode.name)

                        elif isinstance(ast_node, ast.ImportFrom):
                            if ast_node.module is None:
                                current_path = root
                                for obj_import in ast_node.names:
                                    if not _add_new_node(current_path, obj_import.name, ast_node.lineno, nodes, node, full_path):
                                        _add_missing_module(missing_modules, current_path, module)
                            else:
                                current_path = root_path
                                if 0 <= ast_node.lineno - 1 < len(lines) and\
                                        REGEX_RELATIVE_PATTERN.findall(lines[ast_node.lineno - 1]):
                                    current_path = root

                                if not _add_new_node(current_path, ast_node.module, ast_node.lineno, nodes, node, full_path):
                                    for obj_import in ast_node.names:
                                        module = ast_node.module + '.' + obj_import.name
                                        if not _add_new_node(current_path, module, ast_node.lineno, nodes, node, full_path):
                                            _add_missing_module(missing_modules, current_path, module)
                                else:
                                    for obj_import in ast_node.names:
                                        if ast_node.lineno not in node.func_imports:
                                            node.func_imports[ast_node.lineno] = [obj_import.name]
                                        else:
                                            node.func_imports[ast_node.lineno].append(obj_import.name)

                        elif isinstance(ast_node, (ast.ClassDef, ast.FunctionDef)):
                            node.func_defs[ast_node.name] = ast_node.lineno

                except Exception as e:
                    errors = True
                    click.echo(crayons.yellow('Parsing of file failed: {}'.format(full_path)))
                    if verbose:
                        click.echo(crayons.red(traceback.format_exc(e)))

    if errors:
        click.echo(crayons.red('There were errors during the operation, perhaps you are trying to parse python 3 project, '
                               'with python 2 version of the script? (or vice versa)'))

    root_nodes = [node for node in nodes.values() if len(node.is_imported_from) == 0]
    additional_roots = [node for node in nodes.values() if (node not in root_nodes) and not node.is_imported_from_any(root_nodes)]
    return root_nodes + additional_roots


def get_path_from_package_name(root: Optional[str], pkg: Optional[str]) -> str:
    if not pkg or not root:
        return ''
    modules = pkg.split(".")
    return os.path.join(os.path.normpath(root), os.sep.join(modules) + '.py')


def _register_cycle(cycles: Dict[str, List[Node]], path: List, node: Node) -> None:
    """Register detected cycle

    :param cycles: list of all detected cycles,
                - key is node name, where cycle was detected
                - value is path from the node to the node (e.g. description of the cycle)
    :param path: current path from root to the node
    :param node: where the cycle was detected
    """
    ind = path.index(node)
    assert ind >= 0
    path = list(path[ind:])  # strip path, so it starts in the node
    cur_path = cycles.get(node.name)
    if (cur_path is not None) and (len(cur_path) < len(path)):
        return  # ignore path if there is already shorter path; #TODO this is simplified solution: there might be two different cycles of the same length
    cycles[node.name] = path


def _detect_cycles(node: Node, path: List[Node], cycles: Dict[str, List[Node]], verbose: bool) -> bool:
    """Helper recursive function to find cycles for the parsed node.

    :param node: current node to search for a cycle
    :param path: current path to the node
    :param cycles: result of the operation, key is name of the node, where the cycle was found; value is path from the node to the node
    :param verbose: to print debug info
    :return:
    """
    result = False
    if node in path:
        _register_cycle(cycles, path, node)
        return True

    new_path = list(path)
    new_path.append(node)
    if verbose:
        path_str = '/'.join([node.name for node in new_path])
        click.echo(crayons.white(f'Checking path: {path_str}'))
    for item in node.imports:
        if _detect_cycles(item, new_path, cycles, verbose):
            result = True
    return result


class CyclePath:
    """This class is used to remove duplicated path"""

    def __init__(self, path: List[Node]):
        """Constructor
        :param path: list of nodes
        """
        self.path = path

    def __hash__(self):
        """:return:calculate hash as a sun of hashes of all nodes"""
        result = 0
        for node in self.path:
            result += hash(node)
        return result

    def __eq__(self, other) -> bool:
        """Test for equal paths.

        Two paths compared by nodes: they are same if contains same nodes
        """
        if isinstance(other, CyclePath):
            return set(self.path).__eq__(set(other.path))
        return False

    def description(self) -> str:
        """Converts the path into human readable description, including colors.

        :return: string description of the path to be displayed for the user
        """
        if len(self.path) > 1:
            result = [crayons.yellow(self.path[0].name)]

            previous = self.path[0]
            for item in self.path[1:]:
                result.append(' -> ')
                result.append(crayons.yellow(item.name))
                result.append(': Line ')
                result.append(crayons.cyan(str(item.is_imported_from[previous.full_path][0])))
                previous = item
            result.append(' =>> ')

            result.append(crayons.magenta(self.path[0].name))
            return ''.join(str(x) for x in result)
        else:
            return ''


def detect_cycles(nodes: Iterable[Node], verbose: bool = False) -> List[str]:
    """Detected cycles in given nodes

    :param nodes: dictionary of parse nodes, key is ???, value is Node instance
    :param verbose: True to report detailed info about progress (for debugging)
    :return: list of found cycles
    """
    cycles = dict()
    # first detect cycles from root nodes
    for node in nodes:
        if len(node.is_imported_from) == 0:
            if verbose:
                click.echo(crayons.yellow('### Checking root node: ' + node.name))
            _detect_cycles(node, list(), cycles, verbose)
    # second detect cycles from non-root nodes
    for node in nodes:
        if len(node.is_imported_from) > 0:
            if verbose:
                click.echo(crayons.yellow('### Checking non-root node: ' + node.name))
            _detect_cycles(node, list(), cycles, verbose)

    # remove duplicated cycles with preserving an order (e.g. kept first detected cycle)
    cycles_list = []
    for path in cycles.values():
        cycle_path = CyclePath(path)
        if cycle_path not in cycles_list:
            cycles_list.append(cycle_path)

    # convert cycles into list of strings, one string per one issue found
    return [path.description() for path in cycles_list]
