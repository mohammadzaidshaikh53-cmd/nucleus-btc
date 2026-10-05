"""Negotiated SV2 workspace represented explicitly, with bounded materialization."""
from ..family_ir import Dimension,DimensionKind as D,HeaderFamily
from .sv2_client import VERSION_MASK

def channel_family(client,nonce_bits=tuple(range(32)),version_bits=None,time_bits=(),max_time=None,extranonce_bits=()):
    header,_=client.channel.work();job=client.channel.jobs[client.channel.active]
    rolling=not client.flags&1 and (not client.extended or job.rolling)
    version_bits=tuple(b for b in range(32) if (VERSION_MASK>>b)&1) if version_bits is None and rolling else tuple(version_bits or ())
    if version_bits and not rolling:raise ValueError('Upstream prohibited rolling')
    dims=[Dimension(D.NONCE32,tuple(nonce_bits),0xffffffff,'SV2 nonce',True,True)]
    if version_bits:dims.append(Dimension(D.VERSION_ROLL_BITS,version_bits,VERSION_MASK,'SV2 NewMiningJob/BIP323 or explicit ExtendedJob rolling flag',True,True))
    if time_bits:
        if max_time is None:raise ValueError('Explicit local/consensus timestamp tolerance required')
        dims.append(Dimension(D.NTIME,tuple(time_bits),0xffffffff,'SV2 ntime_start plus explicit local bound',True,True))
    kwargs={}
    if extranonce_bits:
        if not client.extended:raise ValueError('Standard jobs do not permit derived Merkle changes')
        dims.append(Dimension(D.EXTRANONCE,tuple(extranonce_bits),(1<<(8*client.channel.size))-1,'SV2 negotiated extended extranonce size',False,True))
        kwargs={'coinbase_prefix':job.prefix+client.channel.prefix,'coinbase_suffix':job.suffix,
                'extranonce':client.channel.extranonce,'merkle_branch':job.branch}
    return HeaderFamily(header,tuple(dims),header.timestamp,max_time,**kwargs)
