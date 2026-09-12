"""Maintainer tool: lock exact upstream revisions, sizes and SHA-256 hashes."""
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
cache = {}


def api(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "H3-Chat"}), timeout=45) as r:
        return json.load(r)


def component(repo, suffix, role):
    if repo not in cache:
        info = api(f"https://huggingface.co/api/models/{repo}?blobs=true")
        cache[repo] = info
    info = cache[repo]
    matches = [f for f in info["siblings"] if f["rfilename"] == suffix] or [f for f in info["siblings"] if f["rfilename"].lower().endswith(suffix.lower()) and (role != "model" or "mmproj" not in f["rfilename"])]
    if len(matches) != 1:
        raise ValueError(f"{repo}: {suffix}: {[f['rfilename'] for f in info['siblings']]}")
    item = matches[0]
    sha = item.get("lfs", {}).get("sha256")
    if not sha:
        raise ValueError(f"Missing LFS SHA: {item}")
    name = item["rfilename"]
    return {"role": role, "repo": repo, "revision": info["sha"], "filename": name,
            "url": f"https://huggingface.co/{repo}/resolve/{info['sha']}/{name}",
            "path": "models/files/" + sha[:16] + "-" + Path(name).name,
            "size": item["size"], "sha256": sha}


def main():
    models = []
    def model(id, name, capabilities, description, components, **extra):
        files = [component(*entry) for entry in components]
        models.append(dict(id=id, name=name, capabilities=capabilities, description=description,
                           files=files, size=sum(f["size"] for f in files), **extra))
        print(id, "OK", round(sum(f["size"] for f in files)/1e9, 2), "GB", flush=True)

    model("qwen3-06", "Qwen3 · 0.6B Q4", ["chat"], "Chat e router leggeri. Ideale per CPU; ragionamento e routing limitati rispetto ai modelli più grandi.",
          [("unsloth/Qwen3-0.6B-GGUF", "Q4_K_M.gguf", "model")], license="Apache-2.0", ram_gb=3, max_refs=0)
    model("qwen3-4", "Qwen3 · 4B Q4", ["chat"], "Chat, codice e instradamento. Profilo consigliato per 4–8 GB di VRAM.",
          [("unsloth/Qwen3-4B-GGUF", "Q4_K_M.gguf", "model")], license="Apache-2.0", ram_gb=6, max_refs=0)
    model("smolvlm", "SmolVLM · 500M Vision", ["chat", "vision"], "Vision essenziale per una sola immagine, principalmente in inglese. Non consigliato per italiano, grafici o documenti: scegli Qwen2.5-VL per queste attività.",
          [("ggml-org/SmolVLM-500M-Instruct-GGUF", "SmolVLM-500M-Instruct-Q8_0.gguf", "model"),
           ("ggml-org/SmolVLM-500M-Instruct-GGUF", "mmproj-SmolVLM-500M-Instruct-f16.gguf", "mmproj")], license="Apache-2.0", ram_gb=3, max_refs=1)
    model("qwen25-vl3", "Qwen2.5-VL · 3B Vision Q4", ["chat", "vision"], "Vision, OCR, codice, lettura di grafici e diagrammi. I valori stimati vanno verificati.",
          [("ggml-org/Qwen2.5-VL-3B-Instruct-GGUF", "Q4_K_M.gguf", "model"),
           ("ggml-org/Qwen2.5-VL-3B-Instruct-GGUF", "mmproj-Qwen2.5-VL-3B-Instruct-f16.gguf", "mmproj")], license="Qwen Research", ram_gb=6, max_refs=4)
    model("sd15", "Stable Diffusion · 1.5", ["create", "edit"], "Immagini a 512 px e trasformazione img2img di una foto. Non è editing semantico multi-riferimento.",
          [("stable-diffusion-v1-5/stable-diffusion-v1-5", "v1-5-pruned-emaonly.safetensors", "model")],
          architecture="sd", license="CreativeML Open RAIL-M", ram_gb=6, max_refs=1, cfg=7)
    model("flux2-klein4", "FLUX.2 klein · 4B Q4", ["create", "edit"], "Creazione e modifica guidata da fino a quattro riferimenti. Include encoder Qwen3 e VAE; su poca VRAM usa la RAM.",
          [("leejet/FLUX.2-klein-4B-GGUF", "Q4_0.gguf", "diffusion"),
           ("unsloth/Qwen3-4B-GGUF", "Q4_K_M.gguf", "llm"),
           ("Comfy-Org/flux2-dev", "flux2-vae.safetensors", "vae")],
          architecture="flux2", license="Apache-2.0 (modello klein); vedi licenze componenti", ram_gb=16, max_refs=4, steps=4, cfg=1)
    (ROOT / "catalog.json").write_text(json.dumps(models, ensure_ascii=False, indent=2), encoding="utf-8")

    llama = json.loads((ROOT / "work/llama-release.json").read_text(encoding="utf-8-sig"))
    sd = json.loads((ROOT / "work/sd-release.json").read_text(encoding="utf-8-sig"))
    runtimes = {}
    for backend in ("cpu", "vulkan", "cuda"):
        files = []
        for engine, release in (("llama", llama), ("sd", sd)):
            needle = {"cpu": "win-cpu-x64.zip", "vulkan": "win-vulkan-x64.zip", "cuda": "win-cuda-12.4-x64.zip" if engine == "llama" else "win-cuda12-x64.zip"}[backend]
            assets = [a for a in release["assets"] if a["name"].endswith(needle) and not a["name"].startswith("cudart")]
            if backend == "cuda":
                rt = "cudart-llama-bin-win-cuda-12.4-x64.zip" if engine == "llama" else "cudart-sd-bin-win-cu12-x64.zip"
                assets += [a for a in release["assets"] if a["name"] == rt]
            if len(assets) != (2 if backend == "cuda" else 1):
                raise ValueError((backend, engine, "assets missing"))
            for asset in assets:
                files.append({"path": "runtime/archives/" + asset["name"], "url": asset["browser_download_url"],
                              "size": asset["size"], "sha256": asset["digest"].split(":")[1],
                              "extract_to": f"runtime/{backend}/{engine}", "version": release["tag_name"]})
        runtimes[backend] = {"files": files}
    (ROOT / "runtimes.json").write_text(json.dumps(runtimes, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
