from math import log

def slope(points):
    positive=[(log(k),log(v)) for k,v in points if k>0 and v>0]
    if len(positive)<3: return None
    xm=sum(x for x,y in positive)/len(positive);ym=sum(y for x,y in positive)/len(positive)
    denominator=sum((x-xm)**2 for x,y in positive)
    return sum((x-xm)*(y-ym) for x,y in positive)/denominator if denominator else None

def fitness(correct,ordinary_total,new_total,construction=0,transition=0,hunt=0,rho=0,proof=0,remaining_fraction=1):
    if not correct: return {"eligible":False,"effective_speedup":0}
    if ordinary_total<=0 or new_total<=0 or not 0<=rho<=1 or proof<0: raise ValueError("Invalid family economics")
    F=proof/ordinary_total;phi=remaining_fraction
    return {"eligible":True,"effective_speedup":ordinary_total/new_total,"F":F,"rho":rho,
            "Q":rho/F if F else None,"pruning_speedup":1/(F+(1-rho)*phi) if F+(1-rho)*phi else None,
            "construction_seconds":construction,"transition_seconds":transition,"hunt_seconds":hunt,
            "total_cost_seconds":new_total,"all_costs_included":True}
