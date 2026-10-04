#include "nucleus/sha256.hpp"
#include <limits>
#ifdef _WIN32
#define NB_EXPORT extern "C" __declspec(dllexport)
#else
#define NB_EXPORT extern "C" __attribute__((visibility("default")))
#endif
using namespace nucleus;

NB_EXPORT int nb_hash_headers(const unsigned char* headers,std::uint64_t count,unsigned char* out) {
    if(!headers||!out||count>std::numeric_limits<std::size_t>::max()/80)return -1;
    for(std::uint64_t i=0;i<count;++i){u32 s[8];header_hash(headers+80*i,s);store_digest(s,out+32*i);}
    return 0;
}
NB_EXPORT int nb_hash_nonces(const unsigned char* header,u32 start,std::uint64_t count,unsigned char* out,int reuse) {
    if(!header||!out||count>(std::uint64_t(1)<<32)-start)return -1;
    u32 mid[8],tail[3];midstate(header,mid);
    for(unsigned i=0;i<3;++i)tail[i]=load_be(header+64+4*i);
    for(std::uint64_t i=0;i<count;++i){
        u32 s[8];if(reuse)finish(mid,tail,start+static_cast<u32>(i),s);
        else { unsigned char copy[80];for(unsigned j=0;j<80;++j)copy[j]=header[j];
            u32 n=start+static_cast<u32>(i);for(unsigned j=0;j<4;++j)copy[76+j]=static_cast<unsigned char>(n>>(8*j));header_hash(copy,s); }
        store_digest(s,out+32*i);
    }return 0;
}
NB_EXPORT int nb_scan_nonces(const unsigned char* header,u32 start,std::uint64_t count,const u32* target,u32* nonces,u32 capacity,std::uint64_t* found,int reuse) {
    if(!header||!target||!nonces||!found||count>(std::uint64_t(1)<<32)-start)return -1;
    u32 mid[8],tail[3];midstate(header,mid);for(unsigned i=0;i<3;++i)tail[i]=load_be(header+64+4*i);
    *found=0;
    for(std::uint64_t i=0;i<count;++i){u32 s[8];u32 n=start+static_cast<u32>(i);
        if(reuse)finish(mid,tail,n,s);
        else {unsigned char copy[80];for(unsigned j=0;j<80;++j)copy[j]=header[j];for(unsigned j=0;j<4;++j)copy[76+j]=static_cast<unsigned char>(n>>(8*j));header_hash(copy,s);}
        if(meets(s,target)){if(*found<capacity)nonces[*found]=n;++*found;}
    }return 0;
}
