from rip import pred

class DBIter:
    def __init__(self, iterable):
        self._it = iter(iterable)

    def __iter__(self):
        return self

    def __next__(self):
        return next(self._it)

    def as_list(self):
        return [i for i in self._it]

    def sort(self, keyfct, reverse=False):
        return DBIter(sorted(self._it, key=keyfct, reverse=reverse))

    def fltr(self, *filters):
        result = self
        for f in filters:
            result = f(result)

        return DBIter(result)

    def all(self, **kwargs):
        result = self

        for key,value in kwargs.items():
            result=result.fltr(pred.is_equal(key, value))

        return result

    def get(self, **kwargs):
        result = self.all(**kwargs)

        try:
            return next(result)
        except StopIteration:
            return None

class DB:
    """Simple highly ineficient "database" to store stream data
    """

    def __init__(self):
        self._db = []

    def __iter__(self):
        return DBIter(self._db)

    def append(self, **kwargs):
        self._db.append(kwargs)

    def sort(self, keyfct, reverse=False):
        return self.__iter__().sort(keyfct, reverse=reverse)

    def fltr(self, *preds):
        return self.__iter__().fltr(*preds)

    def get(self, **kwargs):
        return self.__iter__().get(**kwargs)

    def all(self, **kwargs):
        return self.__iter__().all(**kwargs)
