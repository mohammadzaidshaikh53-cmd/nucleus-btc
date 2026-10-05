from dataclasses import dataclass

MASK=0xFFFFFFFF
COMMUTATIVE={"XOR","AND","OR","ADD32"}
ARITY={"INPUT":0,"CONST32":0,"XOR":2,"AND":2,"OR":2,"NOT":1,
       "ROTR":1,"SHR":1,"SHL":1,"MUX":3}

@dataclass(frozen=True)
class Node:
    op:str
    args:tuple[int,...]=()
    value:int|str|None=None

def execute(node,values,inputs):
    a=[values[i] for i in node.args];op=node.op
    if op=="INPUT":
        value=inputs[node.value]
        if not isinstance(value,int) or not 0<=value<=MASK:raise ValueError("IR inputs must be uint32")
        return value
    if op=="CONST32":return node.value
    if op=="XOR":value=a[0]^a[1]
    elif op=="AND":value=a[0]&a[1]
    elif op=="OR":value=a[0]|a[1]
    elif op=="NOT":value=~a[0]
    elif op=="ADD32":value=sum(a)
    elif op=="ROTR":value=a[0] if node.value==0 else (a[0]>>node.value)|(a[0]<<(32-node.value))
    elif op=="SHR":value=a[0]>>node.value
    elif op=="SHL":value=a[0]<<node.value
    elif op=="MUX":value=(a[0]&a[1])|(~a[0]&a[2])
    else:raise ValueError("Unknown IR opcode")
    return value&MASK
