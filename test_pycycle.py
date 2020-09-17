from __future__ import print_function

import os

import pycycle.utils


def test_get_path_from_package_name():
    func = pycycle.utils.get_path_from_package_name
    assert func('/test/one/two', 'some.package') == os.path.normpath('/test/one/two/some/package.py')
    assert func('', 'some.package') == ''
    assert func('/', None) == ''
    assert func(None, 'some.package') == ''
    assert func('/test/', 'some_package') == os.path.normpath('/test/some_package.py')


def test_simple_project():
    project = {'path': os.path.abspath('./tests/_projects/a_references_b_b_references_a'),
               'has_cycle': True,
               'result': 'a_module -> b_module: Line 1 =>> a_module$$$'
                         'some_package.c_module -> a_module: Line 1 =>> some_package.c_module'}

    nodes = pycycle.utils.read_project(project['path'])
    assert nodes
    assert bool(pycycle.utils.detect_cycles(nodes)) == project['has_cycle']
    assert '$$$'.join(pycycle.utils.detect_cycles(nodes)) == project['result']


def test_no_circular_imports():
    project = {'path': os.path.abspath('./tests/_projects/has_no_circular_imports'),
               'has_cycle': False,
               'result': ''}
    nodes = pycycle.utils.read_project(project['path'])
    assert nodes is not None
    assert bool(pycycle.utils.detect_cycles(nodes)) == project['has_cycle']
    assert '$$$'.join(pycycle.utils.detect_cycles(nodes)) == ''


def test_large_circle():
    project = {'path': os.path.abspath('./tests/_projects/large_circle'),
               'has_cycle': True,
               'result': 'a_package.a_file -> d_package.d_file: Line 2 =>> a_package.a_file$$$'
                         'a_package.b_package.b_file -> c_package.c_file: Line 1 -> d_package.d_file: Line 1 -> a_package.a_file: Line 1 =>> '
                         'a_package.b_package.b_file'}

    nodes = pycycle.utils.read_project(project['path'])
    assert nodes is not None
    assert bool(pycycle.utils.detect_cycles(nodes)) == project['has_cycle']
    assert '$$$'.join(pycycle.utils.detect_cycles(nodes)) == project['result']


def test_large_no_circle():
    project = {'path': os.path.abspath('./tests/_projects/large_without_circle'),
               'has_cycle': False,
               'result': ''}
    nodes = pycycle.utils.read_project(project['path'])
    assert nodes is not None
    assert bool(pycycle.utils.detect_cycles(nodes)) == project['has_cycle']
    assert '$$$'.join(pycycle.utils.detect_cycles(nodes)) == ''


def test_relative_imports():
    project = {'path': os.path.abspath('./tests/_projects/relative_imports'),
               'has_cycle': True,
               'result': 'myapp.models -> myapp.managers: Line 1 =>> myapp.models'}
    nodes = pycycle.utils.read_project(project['path'])
    assert nodes is not None
    assert bool(pycycle.utils.detect_cycles(nodes)) == project['has_cycle']
    assert '$$$'.join(pycycle.utils.detect_cycles(nodes)) == project['result']


def test_import_context():
    project = {'path': os.path.abspath('./tests/_projects/large_circle_context'),
               'has_cycle': True,
               'result': ''}
    nodes = pycycle.utils.read_project(project['path'])
    assert nodes is not None
    assert bool(pycycle.utils.detect_cycles(nodes)) == project['has_cycle']
