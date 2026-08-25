"""Send worker updates to the notebook's UI loop when one is available."""
def make_dispatcher():
    from IPython import get_ipython
    shell = get_ipython()
    kernel = getattr(shell, 'kernel', None)
    loop = getattr(kernel, 'io_loop', None)
    if loop is None:
        return lambda callback: callback()
    return lambda callback: loop.add_callback(callback)
