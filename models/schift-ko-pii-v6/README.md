# Bundled model input

Place the licensed `schift-io/schift-ko-pii-v6` model snapshot in this directory before running the Windows build.

The build script requires at least `config.json`, `tokenizer.json`, `tokenizer_config.json`, `model.safetensors`, `modeling_lfm2_bidirectional.py`, and the model license file. Runtime code only reads this local directory and sets Hugging Face offline flags before model imports.
