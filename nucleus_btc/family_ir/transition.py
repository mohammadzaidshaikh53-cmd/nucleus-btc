from .word import FamilyWord
from ..representations.bitslice import encode_words,decode_words

MODES=("affine-family","carry-residual","DAG","bitplane","native")

def convert(word,mode):
    if mode not in MODES: raise ValueError("Unknown representation")
    if mode=="affine-family": return FamilyWord(tuple(word.materialize(i) for i in range(len(word.values))))
    if mode=="bitplane": return FamilyWord(tuple(decode_words(encode_words(word.values),len(word.values))))
    if mode=="DAG":
        # Canonical finite lookup DAG: shared uint32 leaves plus index edges.
        pool={v:i for i,v in enumerate(dict.fromkeys(word.values))};leaves=tuple(pool)
        return FamilyWord(tuple(leaves[pool[v]] for v in word.values))
    return FamilyWord(tuple(word.values),word.carry_residual if mode=="carry-residual" else ())
