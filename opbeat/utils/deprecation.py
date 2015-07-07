import warnings
import functools


# https://wiki.python.org/moin/PythonDecoratorLibrary#Smart_deprecation_warnings_.28with_valid_filenames.2C_line_numbers.2C_etc..29

def deprecated(alternative=None):
    '''This is a decorator which can be used to mark functions
    as deprecated. It will result in a warning being emitted
    when the function is used.'''
    def real_decorator(func):
        @functools.wraps(func)
        def new_func(*args, **kwargs):
            msg = "Call to deprecated function {}.".format(func.__name__)
            if alternative:
                msg += " Use {} instead".format(alternative)
            warnings.warn_explicit(
                msg,
                category=DeprecationWarning,
                filename=func.func_code.co_filename,
                lineno=func.func_code.co_firstlineno + 1
            )
            return func(*args, **kwargs)
        return new_func
    return real_decorator