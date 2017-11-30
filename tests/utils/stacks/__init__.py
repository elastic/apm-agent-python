import inspect


def get_me_a_test_frame():
    a_local_var = 42
    return inspect.currentframe()
