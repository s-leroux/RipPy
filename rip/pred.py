def is_equal(key, value):
    def _f(seq):
        return (i for i in seq if i.get(key) == value)
    return _f

def is_in(key, values):
    def _f(seq):
        return (i for value in values for i in seq if i.get(key) in values)
    return _f

def order_by(key, values):
    def _f(seq):
        seq = [ i for i in seq ] ### realize sequence
        return (i for value in values for i in seq if i.get(key) == value)
    return _f

def having(key):
    def _f(seq):
        return (i for i in seq if key in i)
    return _f
