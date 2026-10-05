// Optional, unverified without HIP/rocWMMA. Only exact Boolean preprocessing.
#include <hip/hip_runtime.h>
#include <rocwmma/rocwmma.hpp>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <vector>
using namespace rocwmma;

__global__ void transform(const float16_t* a, const float16_t* b, float* out) {
    const unsigned row=blockIdx.y*16, col=blockIdx.x*16;
    fragment<accumulator,16,16,16,float> c;
    fill_fragment(c,0.0f);
    for(unsigned k=0;k<32;k+=16) {
        fragment<matrix_a,16,16,16,float16_t,row_major> x;
        fragment<matrix_b,16,16,16,float16_t,row_major> y;
        load_matrix_sync(x,a+row*32+k,32);
        load_matrix_sync(y,b+k*32+col,32);
        mma_sync(c,x,y,c);
    }
    store_matrix_sync(out+row*32+col,c,32,mem_row_major);
}

static uint32_t rr(uint32_t x,unsigned n) {return (x>>n)|(x<<(32-n));}
template<class T> struct Device {
    T* p=nullptr;
    ~Device() {if(p) hipFree(p);}
    bool allocate(size_t n) {return hipMalloc(reinterpret_cast<void**>(&p),n*sizeof(T))==hipSuccess;}
};

int main() {
    constexpr unsigned count=4096;
    std::vector<uint32_t> words(count),expected(count);
    uint32_t seed=981203;
    for(auto& w:words) {seed=1664525*seed+1013904223;w=seed;}
    auto start=std::chrono::steady_clock::now();
    for(unsigned i=0;i<count;++i) expected[i]=rr(words[i],6)^rr(words[i],11)^rr(words[i],25);
    double scalar=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
    start=std::chrono::steady_clock::now();
    std::vector<float16_t> a(count*32),b(32*32);
    std::vector<float> output(count*32);
    for(unsigned i=0;i<count;++i) for(unsigned j=0;j<32;++j) a[i*32+j]=float16_t((words[i]>>j)&1);
    for(unsigned i=0;i<32;++i) for(unsigned j=0;j<32;++j)
        b[i*32+j]=float16_t(i==(j+6)%32 || i==(j+11)%32 || i==(j+25)%32);
    Device<float16_t> da,db;Device<float> dc;
    if(!da.allocate(a.size()) || !db.allocate(b.size()) || !dc.allocate(output.size())) return 2;
    if(hipMemcpy(da.p,a.data(),a.size()*sizeof(float16_t),hipMemcpyHostToDevice)!=hipSuccess ||
       hipMemcpy(db.p,b.data(),b.size()*sizeof(float16_t),hipMemcpyHostToDevice)!=hipSuccess) return 3;
    hipLaunchKernelGGL(transform,dim3(2,count/16),dim3(32),0,0,da.p,db.p,dc.p);
    if(hipGetLastError()!=hipSuccess || hipDeviceSynchronize()!=hipSuccess ||
       hipMemcpy(output.data(),dc.p,output.size()*sizeof(float),hipMemcpyDeviceToHost)!=hipSuccess) return 4;
    for(unsigned i=0;i<count;++i) {
        uint32_t value=0;
        for(unsigned j=0;j<32;++j) {
            float v=output[i*32+j];
            if(v<0 || v>3 || float(unsigned(v))!=v) return 5;
            value|=(unsigned(v)&1)<<j;
        }
        if(value!=expected[i]) return 6;
    }
    double total=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
    std::printf("{\"exact\":true,\"K\":%u,\"scalar_seconds\":%.9f,\"matrix_all_cost_seconds\":%.9f,\"speedup\":%.9f}\n",count,scalar,total,scalar/total);
}
