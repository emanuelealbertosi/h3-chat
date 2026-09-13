// H3-Chat persistent image worker. Private stdin/stdout protocol; no network listener.
// ABI pinned to stable-diffusion.cpp 7f410a3 (see vendor/SOURCES.json).
#define NOMINMAX
#include <windows.h>
#include <io.h>
#include <fcntl.h>
#include <cstdio>
#include <cmath>
#include <filesystem>
#include <iostream>
#include <map>
#include <memory>
#include <string>
#include <vector>
#include "vendor/stable-diffusion.h"
#include "vendor/json.hpp"
#define STB_IMAGE_IMPLEMENTATION
#define STBI_ONLY_JPEG
#define STBI_ONLY_PNG
#define STBI_NO_HDR
#define STBI_NO_LINEAR
#include "vendor/stb_image.h"
#define STB_IMAGE_WRITE_IMPLEMENTATION
#include "vendor/stb_image_write.h"
using json=nlohmann::json;
static FILE* protocol=nullptr;
static void emit(const json& value){std::string line=value.dump()+"\n";fwrite(line.data(),1,line.size(),protocol);fflush(protocol);}
static std::wstring wide(const std::string& s){int n=MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,s.data(),(int)s.size(),nullptr,0);if(!n)throw std::runtime_error("Invalid UTF-8 path");std::wstring out(n,L' ');MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,s.data(),(int)s.size(),out.data(),n);return out;}

struct Api {
 HMODULE dll=nullptr;
#define FN(name) decltype(&::name) p_##name=nullptr;
 FN(sd_commit) FN(sd_ctx_params_init) FN(new_sd_ctx) FN(free_sd_ctx)
 FN(sd_img_gen_params_init) FN(generate_image) FN(free_sd_images)
 FN(sd_set_progress_callback) FN(sd_get_default_sample_method) FN(sd_get_default_scheduler)
 FN(sd_list_devices) FN(str_to_sample_method) FN(str_to_scheduler) FN(sd_sample_method_name) FN(sd_scheduler_name)
#undef FN
 void open(const std::string& path){
  auto directory=std::filesystem::path(wide(path)).parent_path().wstring();
  SetDllDirectoryW(directory.c_str());
  dll=LoadLibraryExW(wide(path).c_str(),nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
  if(!dll)throw std::runtime_error("Cannot load stable-diffusion.dll: Windows error "+std::to_string(GetLastError()));
#define LOAD(name) p_##name=reinterpret_cast<decltype(p_##name)>(GetProcAddress(dll,#name));if(!p_##name)throw std::runtime_error("Missing native function: " #name);
  LOAD(sd_commit) LOAD(sd_ctx_params_init) LOAD(new_sd_ctx) LOAD(free_sd_ctx)
  LOAD(sd_img_gen_params_init) LOAD(generate_image) LOAD(free_sd_images)
  LOAD(sd_set_progress_callback) LOAD(sd_get_default_sample_method) LOAD(sd_get_default_scheduler)
  LOAD(sd_list_devices) LOAD(str_to_sample_method) LOAD(str_to_scheduler) LOAD(sd_sample_method_name) LOAD(sd_scheduler_name)
#undef LOAD
  std::string commit=p_sd_commit();
  if(commit.find("7f410a3")==std::string::npos)throw std::runtime_error("Native ABI version mismatch: "+commit);
 }
 ~Api(){if(dll)FreeLibrary(dll);}
};

struct InputImage {
 sd_image_t value{};
 explicit InputImage(const std::string& path){
  FILE* file=_wfopen(wide(path).c_str(),L"rb");if(!file)throw std::runtime_error("Cannot open image reference");
  int w=0,h=0,c=0;value.data=stbi_load_from_file(file,&w,&h,&c,3);fclose(file);
  if(!value.data)throw std::runtime_error("Invalid PNG/JPEG reference");
  value.width=w;value.height=h;value.channel=3;
 }
 ~InputImage(){stbi_image_free(value.data);}
};
static void progress(int step,int steps,float seconds,void*){emit({{"event","progress"},{"step",step},{"steps",steps},{"seconds",seconds}});}
static void write_png(const std::string& path,const sd_image_t& image){
 FILE* f=_wfopen(wide(path).c_str(),L"wb");if(!f)throw std::runtime_error("Cannot write output image");
 auto writer=[](void* context,void* data,int size){fwrite(data,1,size,static_cast<FILE*>(context));};
 int ok=stbi_write_png_to_func(writer,f,image.width,image.height,image.channel,image.data,image.width*image.channel);
 bool failed=ferror(f)!=0;fclose(f);if(!ok||failed)throw std::runtime_error("PNG write failed");
}

int main(){
 // Save the protocol pipe, then direct all native-library stdout logging to stderr.
 _setmode(_fileno(stdin),_O_BINARY);_setmode(_fileno(stdout),_O_BINARY);
 protocol=_fdopen(_dup(_fileno(stdout)),"wb");if(!protocol)return 2;
 _dup2(_fileno(stderr),_fileno(stdout));
 Api api;sd_ctx_t* context=nullptr;std::map<std::string,std::string> strings;
 auto text=[&](const std::string& key,const std::string& value)->const char*{strings[key]=value;return strings[key].c_str();};
 try{
  emit({{"event","hello"},{"protocol",1}});
  std::string line;
  while(std::getline(std::cin,line)){
   try{
    if(line.size()>1024*1024)throw std::runtime_error("Worker request too large");
    auto r=json::parse(line);std::string op=r.at("op");
    if(op=="close")break;
    if(op=="probe"){
     api.open(r.at("dll"));size_t size=api.p_sd_list_devices(nullptr,0);std::string devices(size+1,'\0');api.p_sd_list_devices(devices.data(),devices.size());
     emit({{"event","ready"},{"commit",api.p_sd_commit()},{"devices",devices.c_str()}});continue;
    }
    if(op=="load"){
     if(context)throw std::runtime_error("Worker already has a model");
     api.open(r.at("dll"));sd_ctx_params_t p{};api.p_sd_ctx_params_init(&p);
     auto files=r.at("files");
#define PATH(role,field) if(files.contains(role))p.field=text(role,files[role].get<std::string>());
     PATH("model",model_path) PATH("diffusion",diffusion_model_path) PATH("vae",vae_path)
     PATH("clip_l",clip_l_path) PATH("clip_g",clip_g_path) PATH("t5xxl",t5xxl_path)
     PATH("llm",llm_path) PATH("llm_vision",llm_vision_path)
#undef PATH
     p.n_threads=r.value("threads",4);p.enable_mmap=r.value("mmap",true);p.eager_load=true;
     p.backend=text("backend",r.at("backend"));p.params_backend=text("params_backend",r.at("params_backend"));
     p.lora_apply_mode=LORA_APPLY_AT_RUNTIME;
     p.auto_fit=false;p.diffusion_flash_attn=r.value("diffusion_fa",false);
     context=api.p_new_sd_ctx(&p);if(!context)throw std::runtime_error("Model initialization failed");
     api.p_sd_set_progress_callback(progress,nullptr);emit({{"event","ready"},{"commit",api.p_sd_commit()}});continue;
    }
    if(op!="generate"||!context)throw std::runtime_error("No model loaded");
    sd_img_gen_params_t p{};api.p_sd_img_gen_params_init(&p);
    std::string prompt=r.at("prompt"),negative=r.value("negative_prompt",std::string());p.prompt=prompt.c_str();p.negative_prompt=negative.c_str();
    p.width=r.at("width");p.height=r.at("height");p.batch_count=1;p.seed=r.at("seed");p.strength=r.value("strength",.65f);
    p.sample_params.sample_steps=r.at("steps");p.sample_params.guidance.txt_cfg=r.at("cfg");p.sample_params.guidance.img_cfg=r.at("cfg");
    p.sample_params.sample_method=r.value("euler",false)?EULER_SAMPLE_METHOD:api.p_sd_get_default_sample_method(context);
    std::string sampler=r.value("sampler",std::string("auto")),scheduler=r.value("scheduler",std::string("auto"));
    if(sampler!="auto"){p.sample_params.sample_method=api.p_str_to_sample_method(sampler.c_str());if(p.sample_params.sample_method==SAMPLE_METHOD_COUNT)throw std::runtime_error("Unsupported sampler");}
    p.sample_params.scheduler=scheduler=="auto"?api.p_sd_get_default_scheduler(context,p.sample_params.sample_method):api.p_str_to_scheduler(scheduler.c_str());
    if(p.sample_params.scheduler==SCHEDULER_COUNT)throw std::runtime_error("Unsupported scheduler");
    auto selected=r.value("loras",json::array());if(!selected.is_array()||selected.size()>8)throw std::runtime_error("Invalid LoRA selection");
    std::vector<std::string> lora_paths;std::vector<sd_lora_t> loras;lora_paths.reserve(selected.size());loras.reserve(selected.size());
    for(const auto& item:selected){
     float weight=item.at("weight");if(!std::isfinite(weight)||weight < -2||weight > 2)throw std::runtime_error("Invalid LoRA weight");
     lora_paths.push_back(item.at("path"));sd_lora_t lora{};lora.path=lora_paths.back().c_str();lora.multiplier=weight;lora.is_high_noise=false;loras.push_back(lora);
    }
    p.loras=loras.empty()?nullptr:loras.data();p.lora_count=(uint32_t)loras.size();
    // Omitted flow shift must keep the API's automatic value (INFINITY).
    // Zero collapses flow-model timesteps and produces invalid/blank images.
    if(r.contains("flow_shift")){
     float shift=r.at("flow_shift");if(!std::isfinite(shift)||shift<=0)throw std::runtime_error("Invalid flow shift");
     p.sample_params.flow_shift=shift;
    }
    p.vae_tiling_params.enabled=true;
    std::vector<std::unique_ptr<InputImage>> owners;std::vector<sd_image_t> refs;
    for(const auto& path:r.value("references",json::array())){owners.push_back(std::make_unique<InputImage>(path));refs.push_back(owners.back()->value);}
    if(r.value("init_image",false)&&!refs.empty())p.init_image=refs[0];
    else if(!refs.empty()){p.ref_images=refs.data();p.ref_images_count=(int)refs.size();}
    sd_image_t* result=nullptr;int count=0;
    bool ok=api.p_generate_image(context,&p,&result,&count);
    try{
     if(!ok||!result||count<1)throw std::runtime_error("Image generation returned no result");
     write_png(r.at("output"),result[0]);
    }catch(...){if(result)api.p_free_sd_images(result,count);throw;}
    api.p_free_sd_images(result,count);emit({{"event","done"},{"output",r.at("output")},
      {"parameters",{{"seed",p.seed},{"sampler",api.p_sd_sample_method_name(p.sample_params.sample_method)},{"scheduler",api.p_sd_scheduler_name(p.sample_params.scheduler)}}}});
   }catch(const std::exception& error){emit({{"event","error"},{"message",error.what()}});}
  }
 }catch(const std::exception& error){emit({{"event","error"},{"message",error.what()}});}
 if(context)api.p_free_sd_ctx(context);
 fclose(protocol);return 0;
}
