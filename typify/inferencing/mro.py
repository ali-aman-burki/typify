from typify.preprocessing.symbol_table import (
	InstanceTable, 
	DefinitionTable
)

class MROBuilder:

    @staticmethod
    def build_mro(cls: DefinitionTable) -> list[DefinitionTable]:
        if cls in cls.bases:
            return [cls]

        bases_mros = [base.mro[:] for base in cls.bases]
        bases_mros.append(cls.bases[:])

        return [cls] + MROBuilder.c3_merge(bases_mros) 
    
    @staticmethod
    def c3_merge(seqs: list[list[DefinitionTable]]) -> list[DefinitionTable]:
        result = []
        while True:
            seqs = [s for s in seqs if s]
            if not seqs:
                return result
            for seq in seqs:
                candidate = seq[0]
                if all(candidate not in s[1:] for s in seqs):
                    break
            else:
                raise TypeError("Inconsistent hierarchy, no C3 MRO possible")
            result.append(candidate)
            for seq in seqs:
                if seq[0] == candidate:
                    seq.pop(0)

