#include "nucleus/sha256.hpp"
#include <iostream>
#include <iomanip>
#include <string>
#include <stdexcept>
#include <cctype>
int main(int argc,char**argv){
    try {
        if(argc!=3||std::string(argv[1])!="hash") {std::cerr<<"Usage: nucleus-native hash <160 hex header characters>\n";return 2;}
        std::string hex=argv[2];if(hex.size()!=160)throw std::invalid_argument("header length");
        for(unsigned char ch:hex)if(!std::isxdigit(ch))throw std::invalid_argument("hex characters");
        unsigned char header[80],out[32];
        for(unsigned i=0;i<80;++i){std::size_t pos=0;auto x=std::stoul(hex.substr(2*i,2),&pos,16);if(pos!=2)throw std::invalid_argument("hex");header[i]=static_cast<unsigned char>(x);}
        nucleus::u32 state[8];nucleus::header_hash(header,state);nucleus::store_digest(state,out);
        for(auto b:out)std::cout<<std::hex<<std::setw(2)<<std::setfill('0')<<unsigned(b);
        std::cout<<'\n';return 0;
    }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}
}
