class DBIter:
    def __init__(self, iterable):
        self._it = iter(iterable)

    def __iter__(self):
        return self

    def __next__(self):
        return next(self._it)

    def filter(self, attr, values):
        r = [i for i in self._it] # !!! realyze lazy seq.
        return DBIter((item for value in values 
                         for item in r
                             if item.get(attr) == value))

    def having(self, **kwargs):
        result = self
        for key,value in kwargs.items():
            result=result.filter(key, (value,))

        return result

    def find(self, **kwargs):
        result = self.having(**kwargs)

        try:
            return next(result)
        except StopIteration:
            return dict(**kwargs)

    def get(self, **kwargs):
        result = self.having(**kwargs)

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

    def filter(self, attr, values):
        return self.__iter__().filter(attr,values)

    def having(self, **kwargs):
        return self.__iter__().having(**kwargs)

    def get(self, **kwargs):
        return self.__iter__().get(**kwargs)

    def find(self, **kwargs):
        return self.__iter__().find(**kwargs)
