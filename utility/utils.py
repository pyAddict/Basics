import json
from csv import DictReader
from datetime import date, datetime, timedelta
from functools import partial, wraps
from inspect import FullArgSpec, getfullargspec
from logging import getLogger
from os import walk
from os.path import abspath, join
from time import time
from typing import Iterable, Sequence, TypeVar, Dict

from dateutil.parser import parse
from psycopg2 import connect
from psycopg2.extensions import connection
from psycopg2.extras import DictConnection

from utility.logger import LOGGER_NAME

T = TypeVar('T')


# -----------------------------------------------------


class DB:
    '''
    This class provide functionality to create connection object.
    This is helpful in case mulitple object is to made for same credential
    '''

    def __init__(self, *, dbname, user, password, host='localhost', port=5432):
        self.dbname = dbname
        self.user = user
        self.password = password
        self.host = host
        self.port = port

    @property
    def dict_conn(self) -> connection:
        return connect(**self.__dict__, connection_factory=DictConnection)

    @property
    def conn(self) -> connection:
        return connect(**self.__dict__)


# -----------------------------------------------------
class VarArgPresent(Exception):
    pass


def _same_name_as_constructor(ins: FullArgSpec, *args, **kwargs):
    if ins.varargs is not None:
        raise VarArgPresent('variable argument is present.')

    pos_args_names = ins.args

    obj_dict = {}

    obj_dict.update(zip(pos_args_names[1:len(args) + 1], args))

    if ins.defaults is not None:
        key_args_names = ins.args[-len(ins.defaults):]
        obj_dict.update(zip(key_args_names, ins.defaults))

    if ins.kwonlydefaults is not None:
        # when key_only args are also used (* is used)
        obj_dict.update(ins.kwonlydefaults)

    obj_dict.update(**kwargs)  # now overriding with given kwargs
    return obj_dict


def constructor_setter(__init__):
    '''
    This decorator sets objects attribute name same as defined in its constructor.
    kwargs keys also contribute to object attribute along with key only args.

    In case, variable argument is present in constructor, Exception VarArgPresent is thrown.

    :param __init__:
    :return:
    '''

    @wraps(__init__)
    def f(self, *args, **kwargs):
        ins = getfullargspec(__init__)
        self.__dict__.update(_same_name_as_constructor(ins, *args, **kwargs))
        __init__(self, *args, **kwargs)

    return f


def execution_time(func, logger_name: str = LOGGER_NAME):
    '''
    finds time taken to execute a function.
    Function should not be recursive
    :param func:
    :return:
    '''

    @wraps(func)
    def f(*args, **kwargs):
        start_time = time()
        output = func(*args, **kwargs)
        getLogger(logger_name).info('time taken to execute %s: %0.3f seconds',
                                    func.__name__, time() - start_time)
        return output

    return f


# -----------------------------------------------------
def _always_true(f: str) -> bool:
    return True


def _identity(f: str) -> str:
    return f


def _files_inside_dir(dir_name: str, match=_always_true,
                      mapper=_identity) -> str:
    """
    recursively finds all files inside dir and in its subdir recursively
    :param dir_name: top level dir
    :param match: criteria to select file
    :param mapper: transforming selected files
    :return: generator to files
    """

    dir_name = abspath(dir_name)

    for dir_path, _, files in walk(dir_name):
        dir_joiner = partial(join, dir_path)
        for f in map(mapper, filter(match, map(dir_joiner, files))):
            yield f


def files_inside_dir(dir_name: str, match=_always_true,
                     mapper=_identity, as_itr=False) -> Iterable[str]:
    """
    recursively finds all files inside dir and in its subdir recursively
    :param dir_name: top level dir
    :param match: criteria to select file
    :param mapper: transforming selected files
    :param as_itr: if output is required to be iterator
    :return: file path generator / list
    """
    it = _files_inside_dir(dir_name, match=match, mapper=mapper)

    return it if as_itr else list(it)


def get_file_name(file_name: str, at=-1) -> str:
    '''
    Extracts fileName from a file
    :param file_name:
    :param at: fetch name after splitting files on '/'
    :return:
    '''
    return file_name.split('/')[at].split('.')[0]


def json_load(file: str):
    '''
    loads json file.
    :param file:
    :return: loaded json file as dict/list
    '''

    with open(file) as f:
        return json.load(f)


def json_dump(obj, file: str, indent: int = None, default_cast=None,
              sort_keys=False, cls=None):
    '''
    dumps obj in json file.
    :param obj:
    :param file:
    :param indent:
    :param default_cast:
    :param sort_keys:
    :param cls:
    '''
    with open(file, 'w') as f:
        json.dump(obj, f, indent=indent,
                  default=default_cast, sort_keys=sort_keys,
                  cls=cls)


def csv_itr(file: str) -> Iterable[Dict[str, str]]:
    '''
    returns a generator from reading csv file.
    Each row is returned as dictionary.

    :param file:
    :return: row of csv
    '''
    with open(file) as f:
        reader = DictReader(f)
        for doc in reader:
            yield doc


# -----------------------------------------------------
def as_date(date_) -> date:
    '''
    cast date_ to date object.

    :param date_:
    :return: date object from "date_"
    '''
    if isinstance(date_, str):
        date_ = parse(date_)

    if isinstance(date_, datetime):
        date_ = date_.date()

    assert isinstance(date_, date)

    return date_


def date_generator(start_date, end_date, include_end=True, interval=1) -> Iterable[date]:
    '''
    generates dates between start and end date (both inclusive)
    :param start_date:
    :param end_date:
    :param interval:
    :return:
    '''

    start_date = as_date(start_date)
    end_date = as_date(end_date)

    if include_end:
        assert start_date <= end_date
    else:
        assert start_date < end_date
        end_date -= timedelta(days=1)

    td = timedelta(days=interval)

    while start_date <= end_date:
        yield start_date

        start_date += td


# -----------------------------------------------------

def divide_in_chunk(docs: Sequence[T], chunk_size) -> Iterable[Sequence[T]]:
    '''
    divides list of elements in fixed size of chunks.
    Last chunk can have elements less than chunk_size.

    :param docs: list of elements
    :param chunk_size:
    :return: iterator
    '''
    if len(docs) <= chunk_size:
        yield docs
    else:
        for i in range(0, len(docs), chunk_size):
            yield docs[i:i + chunk_size]


def filter_transform(data_stream: Iterable[T], condition, transform) -> Iterable[T]:
    '''
    given a list filters elements and transform filtered element
    :param data_stream:
    :param condition:
    :param transform:
    :return:
    '''

    return map(transform, filter(condition, data_stream))


# ------------ importing function defined only in this module-------------


def get_functions_clazz(module: str) -> Sequence[str]:
    from importlib import import_module
    from inspect import getmembers, getmodule, isfunction, isclass
    from operator import itemgetter

    module = import_module(module)

    def predicate(o: tuple) -> bool:
        n, m = o
        return (getmodule(m) is module and not n.startswith('_')
                and (isclass(m) or isfunction(m)))

    return tuple(map(itemgetter(0), filter(predicate, getmembers(module))))


if __name__ == 'utility.utils':
    __all__ = get_functions_clazz(__name__)