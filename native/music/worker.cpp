// H3-Chat music worker. Apache-2.0 audio.cpp inference, same YuE2 pipeline as H3-Music.
#include "engine/models/yue2/pipeline.h"
#include "engine/models/yue2/request.h"
#include "engine/framework/audio/wav_writer.h"
#include "json.hpp"
#include <cstdio>
#include <fcntl.h>
#include <io.h>
#include <fstream>
#include <iostream>
#include <memory>
using json = nlohmann::json;
namespace yue = engine::models::yue2;
static FILE *wire;
static void emit(const json &v) { const auto s=v.dump()+"\n"; fwrite(s.data(),1,s.size(),wire); fflush(wire); }
static std::filesystem::path path(const json &v) {return std::filesystem::u8path(v.get<std::string>());}
int main() {
  wire=_fdopen(_dup(_fileno(stdout)),"wb"); _dup2(_fileno(stderr),_fileno(stdout));
  _setmode(_fileno(stdin),_O_BINARY);
  emit({{"event","hello"},{"engine","yue2"}});
  std::unique_ptr<engine::core::ExecutionContext> context;
  std::shared_ptr<yue::Yue2Assets> assets;
  std::unique_ptr<yue::Yue2PipelineRuntime> pipeline;
  for(std::string line;std::getline(std::cin,line);) try {
    auto req=json::parse(line); auto op=req.at("op").get<std::string>();
    if(op=="load") {
      const auto files=req.at("files");
      assets=std::make_shared<yue::Yue2Assets>(*yue::load_yue2_assets(path(files.at("model")).parent_path()));
      assets->model_weights=engine::assets::open_tensor_source(path(files.at("model")),"model_weights");
      assets->vae_weights=engine::assets::open_tensor_source(path(files.at("vae")),"vae_weights");
      auto backend=req.at("backend").get<std::string>();
      if(backend!="cpu"&&backend!="cuda")throw std::runtime_error("YuE2 supports CPU or NVIDIA CUDA.");
      engine::core::BackendConfig cfg;
      cfg.type=backend=="cuda"?engine::core::BackendType::Cuda:engine::core::BackendType::Cpu;
      cfg.threads=req.value("threads",8);
      context=std::make_unique<engine::core::ExecutionContext>(cfg);
      const size_t MB=1024ull*1024ull;
      pipeline=std::make_unique<yue::Yue2PipelineRuntime>(*context,assets,
        engine::assets::TensorStorageType::Native,engine::assets::TensorStorageType::Native,
        6144*MB,1536*MB,4096*MB,1536*MB,6144*MB,1536*MB);
      emit({{"event","ready"}});
    } else if(op=="generate") {
      if(!pipeline)throw std::runtime_error("Load a music model first.");
      engine::runtime::TaskRequest input;
      input.text_input=engine::runtime::Transcript{req.at("lyrics").get<std::string>(),""};
      for(const auto &[k,v]:req.at("options").items())input.options[k]=v.is_string()?v.get<std::string>():v.dump();
      input.options["style"]=req.at("style").get<std::string>();
      input.options["cot"]=req.at("cot").get<std::string>();
      input.options["seed"]=std::to_string(req.at("seed").get<uint64_t>());
      if(req.contains("abc")&&!req.at("abc").get<std::string>().empty())input.options["abc"]=req.at("abc").get<std::string>();
      input.options["h3_artifact_dir"]=path(req.at("output")).parent_path().u8string();
      auto parsed=yue::parse_yue2_request(input,assets->config.generation);
      emit({{"event","stage"},{"message","Composizione musicale e sintesi YuE2"}});
      auto audio=pipeline->run(parsed);
      if(audio.samples.empty()||audio.sample_rate<=0||audio.channels<=0)throw std::runtime_error("Empty audio output.");
      engine::audio::write_pcm16_wav(path(req.at("output")),audio.sample_rate,audio.channels,audio.samples);
      pipeline->release_runtime_graphs();
      emit({{"event","done"},{"parameters",{{"sample_rate",audio.sample_rate},{"channels",audio.channels},
        {"duration",double(audio.samples.size())/audio.channels/audio.sample_rate}}}});
    } else throw std::runtime_error("Unknown operation.");
  } catch(const std::exception &e) {emit({{"event","error"},{"message",e.what()}});return 1;}
  return 0;
}
