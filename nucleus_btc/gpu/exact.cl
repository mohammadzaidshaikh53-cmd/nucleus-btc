// SHA-256d, OpenCL 1.2. Configuration changes algebra or unrolling, never correctness.
#ifndef FULL_UNROLL
#define FULL_UNROLL 0
#endif
#ifndef ALT_BOOLEAN
#define ALT_BOOLEAN 0
#endif
__constant uint K[64]={
0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
uint rr(uint x,uint n){return rotate(x,32U-n);}
uint sw(uint x){return (x>>24)|((x>>8)&0xff00U)|((x<<8)&0xff0000U)|(x<<24);}
uint be(__global const uchar* p){return ((uint)p[0]<<24)|((uint)p[1]<<16)|((uint)p[2]<<8)|p[3];}
void init(uint* s){s[0]=0x6a09e667;s[1]=0xbb67ae85;s[2]=0x3c6ef372;s[3]=0xa54ff53a;s[4]=0x510e527f;s[5]=0x9b05688c;s[6]=0x1f83d9ab;s[7]=0x5be0cd19;}
void compress(uint* s,uint* block){
    uint w[64];for(uint i=0;i<16;++i)w[i]=block[i];
#if FULL_UNROLL
#pragma unroll
#endif
    for(uint i=16;i<64;++i){uint x=w[i-15],y=w[i-2];w[i]=w[i-16]+(rr(x,7)^rr(x,18)^(x>>3))+w[i-7]+(rr(y,17)^rr(y,19)^(y>>10));}
    uint a=s[0],b=s[1],c=s[2],d=s[3],e=s[4],f=s[5],g=s[6],h=s[7];
#if FULL_UNROLL
#pragma unroll
#endif
    for(uint i=0;i<64;++i){
#if ALT_BOOLEAN
        uint ch=g^(e&(f^g)),maj=(a&b)|(c&(a|b));
#else
        uint ch=(e&f)^(~e&g),maj=(a&b)^(a&c)^(b&c);
#endif
        uint t1=h+(rr(e,6)^rr(e,11)^rr(e,25))+ch+K[i]+w[i];
        uint t2=(rr(a,2)^rr(a,13)^rr(a,22))+maj;
        h=g;g=f;f=e;e=d+t1;d=c;c=b;b=a;a=t1+t2;
    }
    s[0]+=a;s[1]+=b;s[2]+=c;s[3]+=d;s[4]+=e;s[5]+=f;s[6]+=g;s[7]+=h;
}
void finish(uint* s,uint* b){compress(s,b);for(uint j=0;j<8;++j)b[j]=s[j];b[8]=0x80000000U;for(uint j=9;j<15;++j)b[j]=0;b[15]=256;init(s);compress(s,b);}
__kernel void hash_headers(__global const uchar* in, uint count,__global uchar* out){
    size_t i=get_global_id(0);if(i>=count)return;
    __global const uchar* p=in+i*80;uint s[8],b[16];
    init(s);for(uint j=0;j<16;++j)b[j]=be(p+4*j);compress(s,b);
    for(uint j=0;j<4;++j)b[j]=be(p+64+4*j);b[4]=0x80000000U;for(uint j=5;j<15;++j)b[j]=0;b[15]=640;
    finish(s,b);for(uint j=0;j<8;++j)for(uint k=0;k<4;++k)out[i*32+j*4+k]=(uchar)(s[j]>>(24-8*k));
}
void nonce_hash(__global const uint* mid,__global const uint* tail,uint nonce,uint* s){
    uint b[16];for(uint j=0;j<8;++j)s[j]=mid[j];b[0]=tail[0];b[1]=tail[1];b[2]=tail[2];b[3]=sw(nonce);b[4]=0x80000000U;for(uint j=5;j<15;++j)b[j]=0;b[15]=640;finish(s,b);
}
__kernel void hash_nonces(__global const uint* mid,__global const uint* tail,uint start,uint count,__global uchar* out){
    size_t i=get_global_id(0);if(i>=count)return;uint s[8];nonce_hash(mid,tail,start+(uint)i,s);
    for(uint j=0;j<8;++j)for(uint k=0;k<4;++k)out[i*32+j*4+k]=(uchar)(s[j]>>(24-8*k));
}
__kernel void scan_nonces(__global const uint* mid,__global const uint* tail,uint start,uint count,__global const uint* target,__global uint* out,uint capacity,__global uint* found){
    size_t i=get_global_id(0);if(i>=count)return;uint s[8],n=start+(uint)i;nonce_hash(mid,tail,n,s);
    int pass=1;for(int j=7;j>=0;--j){uint x=sw(s[j]);if(x<target[j])break;if(x>target[j]){pass=0;break;}}
    if(pass){uint slot=atomic_inc(found);if(slot<capacity)out[slot]=n;}
}
