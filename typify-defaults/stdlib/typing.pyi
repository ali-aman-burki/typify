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
	def __class_getitem__(cls, item) -> _UnpackGenericAlias: ...

class Generic: 

	@classmethod
	def __class_getitem__(cls, item) -> _GenericAlias: ...

class Optional(Generic[T]): 

	@classmethod
	def __class_getitem__(cls, item) -> _GenericAlias: ...
	
class Union(Generic[Unpack[Ts]]): 

	@classmethod
	def __class_getitem__(cls, item) -> _GenericAlias: ...
	
class Literal(Generic[Unpack[Ts]]): 

	@classmethod
	def __class_getitem__(cls, item) -> _GenericAlias: ...
	
class Annotated(Generic[T, Unpack[Ts]]): 

	@classmethod
	def __class_getitem__(cls, item) -> _GenericAlias: ...
	
class Final(Generic[T]): 

	@classmethod
	def __class_getitem__(cls, item) -> _GenericAlias: ...
	
class ClassVar(Generic[T]): 

	@classmethod
	def __class_getitem__(cls, item) -> _GenericAlias: ...

class List(Generic[T]): 

	@classmethod
	def __class_getitem__(cls, item) -> _GenericAlias: ...
	
class Set(Generic[T]): 

	@classmethod
	def __class_getitem__(cls, item) -> _GenericAlias: ...
	
class Dict(Generic[K, V]): 

	@classmethod
	def __class_getitem__(cls, item) -> _GenericAlias: ...
	
class Tuple(Generic[Unpack[Ts]]): 

	@classmethod
	def __class_getitem__(cls, item) -> _GenericAlias: ...
	
class FrozenSet(Generic[T]): 

	@classmethod
	def __class_getitem__(cls, item) -> _GenericAlias: ...
	
class DefaultDict(Generic[K, V]): 

	@classmethod
	def __class_getitem__(cls, item) -> _GenericAlias: ...
	
class Counter(Generic[T]): 

	@classmethod
	def __class_getitem__(cls, item) -> _GenericAlias: ...
	
class ChainMap(Generic[K, V]): 

	@classmethod
	def __class_getitem__(cls, item) -> _GenericAlias: ...
	
class Deque(Generic[T]): 

	@classmethod
	def __class_getitem__(cls, item) -> _GenericAlias: ...
	

class Type(Generic[T]): 

	@classmethod
	def __class_getitem__(cls, item) -> _GenericAlias: ...
	
class Generator(Generic[T, V, K]): 

	@classmethod
	def __class_getitem__(cls, item) -> _GenericAlias: ...
	
class AsyncGenerator(Generic[T, V]): 

	@classmethod
	def __class_getitem__(cls, item) -> _GenericAlias: ...
	
class Coroutine(Generic[T, V, K]): 

	@classmethod
	def __class_getitem__(cls, item) -> _GenericAlias: ...
	
class Awaitable(Generic[T]): 

	@classmethod
	def __class_getitem__(cls, item) -> _GenericAlias: ...
	
class AsyncIterable(Generic[T]): 

	@classmethod
	def __class_getitem__(cls, item) -> _GenericAlias: ...
	
class AsyncIterator(AsyncIterable[T], Generic[T]): 

	@classmethod
	def __class_getitem__(cls, item) -> _GenericAlias: ...
	