# calculator/safe_eval.py

import ast
import operator
from typing import Union

# Opérateurs autorisés
OPERATEURS: dict[type, callable] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.Mod: operator.mod
}

def evaluer_expression(expression: str) -> Union[int, float]:
    def _eval(node: ast.AST) -> Union[int, float]:
        if isinstance(node, ast.Num):  # Python <3.8
            return node.n
        elif isinstance(node, ast.Constant):  # Python >=3.8
            return node.value
        elif isinstance(node, ast.BinOp):
            gauche = _eval(node.left)
            droite = _eval(node.right)
            operateur = OPERATEURS[type(node.op)]
            return operateur(gauche, droite)
        elif isinstance(node, ast.UnaryOp):
            operateur = OPERATEURS[type(node.op)]
            operand = _eval(node.operand)
            return operateur(operand)
        else:
            raise TypeError(f"Type de nœud non pris en charge : {type(node)}")

    arbre: ast.Expression = ast.parse(expression, mode='eval')
    return _eval(arbre.body)