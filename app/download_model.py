from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="coqui/XTTS-v2",
    local_dir="storage/models/xtts_v2",
    local_dir_use_symlinks=False
)