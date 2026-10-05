"""Liveness-based register reuse and exact OpenCL/C++ word lowering."""
from collections import Counter

def lower(graph,language="opencl"):
    if language not in ("opencl","cpp"):raise ValueError("Unsupported lowering")
    graph.validate();live=graph.live_nodes();uses=Counter(graph.outputs)
    for i in live:uses.update(graph.nodes[i].args)
    locations={};free=[];registers=0;lines=[]
    for i,n in enumerate(graph.nodes):
        if i not in live:continue
        if n.op=="INPUT":
            prefix,index=n.value[0],int(n.value[1:]);locations[i]=f"{'s' if prefix=='s' else 'block'}[{index}]"
            if prefix not in ("s","w") or index>=(8 if prefix=="s" else 16):raise ValueError("Lowering expects compression input schema")
            continue
        if n.op=="CONST32":locations[i]=f"0x{n.value:08x}U";continue
        a=[locations[j] for j in n.args];op=n.op
        if op in ("XOR","AND","OR","ADD32"):
            expression="("+{"XOR":" ^ ","AND":" & ","OR":" | ","ADD32":" + "}[op].join(a)+")"
        elif op=="NOT":expression=f"(~{a[0]})"
        elif op in ("SHR","SHL"):expression=f"({a[0]} {'>>' if op=='SHR' else '<<'} {n.value})"
        elif op=="MUX":expression=f"bitselect({a[2]}, {a[1]}, {a[0]})" if language=="opencl" else f"(({a[0]} & {a[1]}) | (~{a[0]} & {a[2]}))"
        elif op=="ROTR":expression=f"rotate({a[0]}, {32-n.value}U)" if language=="opencl" else f"(({a[0]} >> {n.value}) | ({a[0]} << {32-n.value}))"
        else:raise ValueError("Unlowerable opcode")
        # Read operands before recycling their slots into this result.
        for j in n.args:
            uses[j]-=1
            if uses[j]==0 and locations[j].startswith("r"):free.append(int(locations[j][1:]))
        register=free.pop() if free else registers
        if register==registers:registers+=1
        locations[i]=f"r{register}";lines.append(f"    r{register} = {expression};")
    lines.extend(f"    s[{i}] = {locations[index]};" for i,index in enumerate(graph.outputs))
    word="uint" if language=="opencl" else "uint32_t"
    declarations="    "+word+" "+", ".join(f"r{i}" for i in range(registers))+";"
    source=f"void compress({word}* s, {word}* block){{\n{declarations}\n"+"\n".join(lines)+"\n}\n"
    return {"source":source,"temporary_registers":registers,"live_nodes":len(live),"language":language}

def kernel_source(graph,template):
    begin=template.index("void compress(");end=template.index("void finish(",begin)
    return template[:begin]+lower(graph)["source"]+template[end:]
