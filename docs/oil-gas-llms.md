# Oil and gas language models (2026-11-17)

What exists on Hugging Face for oil and gas, petroleum and geoscience, what runs on a 16 GB GPU with llama.cpp, what
was downloaded, and how each is set up for different jobs. Hardware: RTX 5060 Ti 16 GB, 31 GB RAM.

## Downloaded, with profiles on the gateway

One model file can have several gateway entries, each with flags tuned for a job. Pick by name (the model picker in
the studio's sidebar lists them). Only one model is loaded at a time; switching takes 30 to 60 s.

| Gateway name | File | Tuned for | What the flags do |
|---|---|---|---|
| `naija-petro-8b` | Naija-Petro 8B (Qwen3-8B, QLoRA on ~20k synthetic petroleum Q&A), Q8_0, 8.7 GB | chat, short answers | all layers on the GPU, 32k context, q8 KV cache, **speculative decoding** with Qwen3-0.6B as the draft (same tokenizer) |
| `naija-petro-8b-extract` | same file | bulk extraction (hazards from well histories, hidden NPT, DISKOS-QA runs) | **4 parallel slots** with continuous batching for throughput, thinking off (`--reasoning-budget 0`), prompt-cache reuse (`--cache-reuse 256`), **n-gram speculation**, which pays off when the answer copies text from the prompt |
| `naija-petro-8b-long` | same file | whole reports, many passages | 64k context via **YaRN** rope scaling (trained to 32k) |
| `naija-petro-32b` | Naija-Petro 32B (Qwen3-32B, same data), Q4_K_M, 19.8 GB | quality | dense: FFN of 34 of 64 layers on the CPU (`--override-tensor`), the rest and the KV cache on the GPU; no draft (see the measurements) |
| `naija-petro-32b-fast` | same file | quick answers | thinking off, 8k context, so only 32 layers' FFN on the CPU |
| `ogai-24b` | GainEnergy OGAI-24B (Mistral Small 24B Instruct 2501 per the GGUF metadata), Q6_K, 19.3 GB | chat with an oil and gas fine-tune | FFN of 15 of 40 layers on the CPU; no draft (see the measurements) |
| `ogai-24b-long` | same file | long documents | 32k context, no draft (its VRAM goes to the KV cache), FFN of 19 layers on the CPU |

Draft models (small, same tokenizer family): `draft-qwen3-0.6b-Q8_0.gguf` (Qwen/Qwen3-0.6B-GGUF) and
`draft-mistral-small-0.5b-Q8_0.gguf` (alamios/Mistral-Small-3.1-DRAFT-0.5B). All files are in `/srv/models`.

**Measured 2026-11-18** (one 200-token answer each, model already loaded after the first call):

| Profile | tokens/s | |
|---|---|---|
| naija-petro-8b, -extract, -long | 48 | whole model on the GPU |
| naija-petro-32b (with draft) | 6.6 | dense, 36 of 64 FFN layers on the CPU |
| naija-petro-32b-fast | 7.1 | no thinking, 32 layers on the CPU |
| ogai-24b (with draft) | 5.1 | dense, 16 of 40 FFN layers on the CPU |
| ogai-24b-long (no draft) | 6.9 | 19 layers on the CPU, still faster |

On the two dense models the draft costs more VRAM (pushing layers to the CPU) than it saves, so it was dropped from
`naija-petro-32b` and `ogai-24b` and their freed VRAM moved two and one FFN layers back to the GPU. Dense models above
16 GB are bound by the CPU share of their weights: 5 to 7 tokens/s is the ceiling on this card; use the 8B for
interactive work and bulk extraction, the big ones for quality.

**Before the measurements the splits were estimates.** They come from file sizes and from how the other dense
models on this gateway were set up. Before relying on them, load each once and read the VRAM line in `kubectl -n llm
logs deploy/llm`; move layers (the digits in the `--override-tensor` pattern) until about 1 GB of VRAM is free, then
time a request. Rules that hold: dense models are bound by the CPU's share of the weights, so more layers on the GPU
is faster; speculative decoding helps most on dense models and on text that copies the prompt; a draft costs VRAM, so
drop it when the context needs the room.

Sources: https://huggingface.co/GainEnergy/OGAI-24B-Q6_K-GGUF, https://huggingface.co/Shinzmann/naija-petro,
https://huggingface.co/Shinzmann/naija-petro-8b (code: https://github.com/Mystique1337/naija-petro). Apache-2.0 for
Naija-Petro and OGAI-24B's GGUF card.

## Looked at, not downloaded

| Model | Why not |
|---|---|
| GainEnergy/OGAI-r1 (TinyR1-32B adapter) | the repository has no weights, only a README |
| GainEnergy/OGAI-8x7b (Mixtral 8x7B LoRA), Q4_K_M GGUF 28.4 GB | fits only with most experts in RAM, which kratos needs for the cluster; the card claims 94.8 % "drilling calculations accuracy" on its own corpus, with no paper. Worth a try later |
| GainEnergy/OGAI-STEM-7B, ogai-reasoner | gated (access request) |
| GeoGPT (Qwen2.5-72B-GeoGPT, Llama3.1-70B-GeoGPT, GeoGPT-R1-Preview) | 70B+, no GGUF; GeoGPT licence. Their GeoEmbedding and GeoReranker are small and could serve retrieval |
| MLee1006/geoscience-ft_gemma-4-26B-A4B-it | safetensors only, no model card |
| PetroGPT/Llama-3-Petro-Instruct-v1, Breeze-Petro-7B | no stated petroleum data (Breeze-Petro: chemistry plus some petroleum, English and Chinese) |
| K2 (geoscience LLaMA 7B, 2023), GeoGalactica (30B) | old, superseded |
| AITeamUIT/gliner2-oil-gas | not a chat model: GLiNER entity extraction for oil and gas text. Useful for pulling wells, formations and fluids out of reports |

## What the research says about domain models

- On FormationEval (Jan 2026, 505 petroleum geoscience questions, 72 models), general frontier models lead:
  Gemini 3 Pro Preview 99.8 %, GLM-4.7 98.6 % (best open weights), GPT-4o 92.9 %. Petrophysics is the hardest
  area. Domain fine-tunes like K2 and GeoGalactica are now mostly of historical interest (see
  research_notes/.../llm_agents_documents.md).
- So the value is in grounding (retrieval over reports, tools over data) and evaluation, not in a petroleum model.
  The fine-tunes above are worth comparing on DISKOS-QA: a small local petroleum model that matches a big general
  one on grounded questions is a result in itself, and it keeps the data on site. The Detective scorecard takes a
  model per run (`X-Model` header, or the picker), so each model gets its own column.

## Try them

Through the gateway, by name (any app, or curl from a pod with the llm access label):

    curl http://llm.llm/v1/chat/completions -d '{"model":"naija-petro-8b","messages":[{"role":"user","content":"What is the Archie equation?"}]}'
