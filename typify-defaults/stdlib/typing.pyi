class Any: ...
class TypeVar: ...
class TypeVarTuple: ...
class NoReturn: ...
class NewType: ...

T = TypeVar('T')
K = TypeVar('K')
V = TypeVar('V')
Ts = TypeVarTuple('Ts')

class _GenericAlias:
    def __init__(self, origin, args) -> None: ...
class _UnpackGenericAlias:
    def __init__(self, origin, args) -> None: ...
	
class Unpack: 

	@classmethod
	def __class_getitem__(cls, item): return _UnpackGenericAlias(cls, item)

class Generic: 

	@classmethod
	def __class_getitem__(cls, item): return _GenericAlias(cls, item)

class Optional(Generic[T]): 

	@classmethod
	def __class_getitem__(cls, item): return _GenericAlias(cls, item)
	
class Union(Generic[Unpack[Ts]]): 

	@classmethod
	def __class_getitem__(cls, item): return _GenericAlias(cls, item)
	
class Literal(Generic[Unpack[Ts]]): 

	@classmethod
	def __class_getitem__(cls, item): return _GenericAlias(cls, item)
	
class Annotated(Generic[T, Unpack[Ts]]): 

	@classmethod
	def __class_getitem__(cls, item): return _GenericAlias(cls, item)
	
class Final(Generic[T]): 

	@classmethod
	def __class_getitem__(cls, item): return _GenericAlias(cls, item)
	
class ClassVar(Generic[T]): 

	@classmethod
	def __class_getitem__(cls, item): return _GenericAlias(cls, item)

class List(Generic[T]): 

	@classmethod
	def __class_getitem__(cls, item): return _GenericAlias(cls, item)
	
class Set(Generic[T]): 

	@classmethod
	def __class_getitem__(cls, item): return _GenericAlias(cls, item)
	
class Dict(Generic[K, V]): 

	@classmethod
	def __class_getitem__(cls, item): return _GenericAlias(cls, item)
	
class Tuple(Generic[Unpack[Ts]]): 

	@classmethod
	def __class_getitem__(cls, item): return _GenericAlias(cls, item)
	
class FrozenSet(Generic[T]): 

	@classmethod
	def __class_getitem__(cls, item): return _GenericAlias(cls, item)
	
class DefaultDict(Generic[K, V]): 

	@classmethod
	def __class_getitem__(cls, item): return _GenericAlias(cls, item)
	
class Counter(Generic[T]): 

	@classmethod
	def __class_getitem__(cls, item): return _GenericAlias(cls, item)
	
class ChainMap(Generic[K, V]): 

	@classmethod
	def __class_getitem__(cls, item): return _GenericAlias(cls, item)
	
class Deque(Generic[T]): 

	@classmethod
	def __class_getitem__(cls, item): return _GenericAlias(cls, item)
	

class Type(Generic[T]): 

	@classmethod
	def __class_getitem__(cls, item): return _GenericAlias(cls, item)
	
class Callable(Generic[Unpack[Ts], T]): 

	@classmethod
	def __class_getitem__(cls, item): return _GenericAlias(cls, item)
	
class Generator(Generic[T, V, K]): 

	@classmethod
	def __class_getitem__(cls, item): return _GenericAlias(cls, item)
	
class AsyncGenerator(Generic[T, V]): 

	@classmethod
	def __class_getitem__(cls, item): return _GenericAlias(cls, item)
	
class Coroutine(Generic[T, V, K]): 

	@classmethod
	def __class_getitem__(cls, item): return _GenericAlias(cls, item)
	
class Awaitable(Generic[T]): 

	@classmethod
	def __class_getitem__(cls, item): return _GenericAlias(cls, item)
	
class AsyncIterable(Generic[T]): 

	@classmethod
	def __class_getitem__(cls, item): return _GenericAlias(cls, item)
	
class AsyncIterator(AsyncIterable[T], Generic[T]): 

	@classmethod
	def __class_getitem__(cls, item): return _GenericAlias(cls, item)
	