"""Bounded equality saturation of local finite-family cones.

Only known uint32 identities generate alternatives. Equivalence classes are
exact output truth tables on the current family; these are not universal proofs.
Cost extraction uses measured lowering, conversion, carry and register proxies.
"""
from time import perf_counter
from .factor import factored_boolean,blocked_sum
from .word import FamilyWord
from ..oracle.sha256 import rotr

class FamilyEGraph:
    def __init__(self,node_budget=32):self.node_budget=node_budget;self.classes={};self.nodes=[]
    def insert(self,name,result,seconds,models):
        if len(self.nodes)>=self.node_budget:raise MemoryError('bounded family equality saturation exhausted')
        signature=result.values;ident=self.classes.setdefault(signature,len(self.classes))
        node={'name':name,'class':ident,'seconds':seconds,'models':models};self.nodes.append(node);return ident
    def extract(self,class_id,model='measured'):
        choices=[n for n in self.nodes if n['class']==class_id]
        return min(choices,key=lambda n:n['seconds'] if model=='measured' else n['models'][model])

def saturate(words,node_budget=32):
    if len(words)!=5:raise ValueError('T1 cone needs five exact family operands')
    graph=FamilyEGraph(node_budget);rows=[]
    ch=(('Ch-canonical',lambda e,f,g:(e&f)^((~e)&g)),('Ch-select',lambda e,f,g:g^(e&(f^g))))
    maj=(('Maj-canonical',lambda a,b,c:(a&b)^(a&c)^(b&c)),('Maj-factored',lambda a,b,c:(a&b)|(c&(a|b))))
    for name,fn in ch+maj:
        t=perf_counter();out,unique=factored_boolean(words[:3],fn);elapsed=perf_counter()-t
        models={'opencl_scalar':len(out.values)*3,'wave32':(len(out.values)+31)//32*3,
                'family_symbolic':unique*3,'carry_residual':unique*32,'register_pressure':3*32}
        graph.insert(name,out,elapsed,models)
    for width in (4,8,16):
        t=perf_counter();out,metric=blocked_sum(words,width);elapsed=perf_counter()-t
        graph.insert(f'blocked-T1-{width}',out,elapsed,{'opencl_scalar':len(out.values)*4,'wave32':(len(out.values)+31)//32*4,
                     'family_symbolic':metric['table_entries'],'carry_residual':metric['Ucarry'],'register_pressure':5*32})
    for name,fn in (('Sigma1-direct',lambda x:rotr(x,6)^rotr(x,11)^rotr(x,25)),
                    ('Sigma1-composed',lambda x:rotr(x,6)^rotr(rotr(x,6),5)^rotr(rotr(x,11),14))):
        t=perf_counter();out,unique=factored_boolean(words[:1],fn);elapsed=perf_counter()-t
        graph.insert(name,out,elapsed,{'opencl_scalar':len(out.values)*5,'wave32':(len(out.values)+31)//32*5,
                                     'family_symbolic':unique*5,'carry_residual':unique*32,'register_pressure':3*32})
    for class_id in sorted(set(n['class'] for n in graph.nodes)):
        rows.append({'equivalence_class':class_id,'members':[n for n in graph.nodes if n['class']==class_id],
                     'measured_extraction':graph.extract(class_id),
                     'cost_model_choices':{model:graph.extract(class_id,model)['name'] for model in ('opencl_scalar','wave32','family_symbolic','carry_residual','register_pressure')}})
    return {'status':'measured','rows':rows,'nodes':len(graph.nodes),'bounded':True,
            'family_equivalence_exhaustive':True,'whole_hash_speedup_demonstrated':False}
