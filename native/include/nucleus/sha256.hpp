#pragma once
#include <cstdint>
#include <cstddef>

#ifdef __HIPCC__
#define NB_HD __host__ __device__
#else
#define NB_HD
#endif

namespace nucleus {
using u32 = std::uint32_t;
NB_HD inline u32 rotr(u32 x, unsigned n) { return (x >> n) | (x << (32-n)); }
NB_HD inline u32 load_be(const unsigned char* p) {
    return (u32(p[0])<<24)|(u32(p[1])<<16)|(u32(p[2])<<8)|u32(p[3]);
}
NB_HD inline u32 swap(u32 x) { return (x>>24)|((x>>8)&0xff00)|((x<<8)&0xff0000)|(x<<24); }
NB_HD inline void init(u32* s) {
    s[0]=0x6a09e667;s[1]=0xbb67ae85;s[2]=0x3c6ef372;s[3]=0xa54ff53a;
    s[4]=0x510e527f;s[5]=0x9b05688c;s[6]=0x1f83d9ab;s[7]=0x5be0cd19;
}
NB_HD inline void compress(u32* s, const u32* block) {
    const u32 k[64]={
        0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
        0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
        0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
        0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
        0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
        0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
        0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
        0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
    u32 w[64];
    for(unsigned i=0;i<16;++i) w[i]=block[i];
    for(unsigned i=16;i<64;++i) {
        u32 x=w[i-15],y=w[i-2];
        w[i]=w[i-16]+(rotr(x,7)^rotr(x,18)^(x>>3))+w[i-7]+(rotr(y,17)^rotr(y,19)^(y>>10));
    }
    u32 a=s[0],b=s[1],c=s[2],d=s[3],e=s[4],f=s[5],g=s[6],h=s[7];
    for(unsigned i=0;i<64;++i) {
        u32 t1=h+(rotr(e,6)^rotr(e,11)^rotr(e,25))+((e&f)^(~e&g))+k[i]+w[i];
        u32 t2=(rotr(a,2)^rotr(a,13)^rotr(a,22))+((a&b)^(a&c)^(b&c));
        h=g;g=f;f=e;e=d+t1;d=c;c=b;b=a;a=t1+t2;
    }
    s[0]+=a;s[1]+=b;s[2]+=c;s[3]+=d;s[4]+=e;s[5]+=f;s[6]+=g;s[7]+=h;
}
NB_HD inline void midstate(const unsigned char* header,u32* s) {
    u32 b[16]; for(unsigned i=0;i<16;++i)b[i]=load_be(header+4*i);
    init(s);compress(s,b);
}
NB_HD inline void finish(const u32* mid,const u32* tail,u32 nonce,u32* s) {
    u32 b[16]={};for(unsigned i=0;i<8;++i)s[i]=mid[i];
    b[0]=tail[0];b[1]=tail[1];b[2]=tail[2];b[3]=swap(nonce);b[4]=0x80000000;b[15]=640;
    compress(s,b);
    for(unsigned i=0;i<8;++i)b[i]=s[i];
    b[8]=0x80000000;for(unsigned i=9;i<15;++i)b[i]=0;b[15]=256;
    init(s);compress(s,b);
}
NB_HD inline void header_hash(const unsigned char* header,u32* s) {
    u32 mid[8],tail[3];midstate(header,mid);
    for(unsigned i=0;i<3;++i)tail[i]=load_be(header+64+4*i);
    u32 nonce=u32(header[76])|(u32(header[77])<<8)|(u32(header[78])<<16)|(u32(header[79])<<24);
    finish(mid,tail,nonce,s);
}
NB_HD inline void store_digest(const u32* s,unsigned char* out) {
    for(unsigned i=0;i<8;++i)for(unsigned j=0;j<4;++j)out[4*i+j]=static_cast<unsigned char>(s[i]>>(24-8*j));
}
NB_HD inline bool meets(const u32* s,const u32* target) {
    for(int i=7;i>=0;--i){u32 x=swap(s[i]);if(x<target[i])return true;if(x>target[i])return false;}
    return true;
}
}
