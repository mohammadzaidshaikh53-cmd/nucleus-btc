#include <hip/hip_runtime.h>
#include "nucleus/sha256.hpp"
#ifdef _WIN32
#define NB_EXPORT extern "C" __declspec(dllexport)
#else
#define NB_EXPORT extern "C"
#endif
__global__ void hash_headers_kernel(const unsigned char* headers,unsigned long long count,unsigned char* output) {
    auto i=static_cast<unsigned long long>(blockIdx.x)*blockDim.x+threadIdx.x;
    if(i>=count)return;
    nucleus::u32 s[8];nucleus::header_hash(headers+80*i,s);nucleus::store_digest(s,output+32*i);
}
NB_EXPORT int nb_hip_hash_headers(const unsigned char* input,unsigned long long count,unsigned char* out) {
    if(!input||!out||!count||count>(1ULL<<24))return -1;
    unsigned char *device_in=nullptr,*device_out=nullptr;
    hipError_t rc=hipMalloc(reinterpret_cast<void**>(&device_in),count*80);
    if(rc!=hipSuccess)return static_cast<int>(rc);
    rc=hipMalloc(reinterpret_cast<void**>(&device_out),count*32);
    if(rc==hipSuccess)rc=hipMemcpy(device_in,input,count*80,hipMemcpyHostToDevice);
    if(rc==hipSuccess){hipLaunchKernelGGL(hash_headers_kernel,dim3((count+255)/256),dim3(256),0,0,device_in,count,device_out);rc=hipGetLastError();}
    if(rc==hipSuccess)rc=hipMemcpy(out,device_out,count*32,hipMemcpyDeviceToHost);
    if(device_out)hipFree(device_out);hipFree(device_in);return static_cast<int>(rc);
}
