"""Exact finite families, distinct from the scalar word IR."""
from .dimensions import Dimension, DimensionKind
from .family import HeaderFamily
from .word import FamilyWord
from .state import evaluate_family

__all__ = ["Dimension", "DimensionKind", "HeaderFamily", "FamilyWord", "evaluate_family"]
