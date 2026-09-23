# 1 Qdrant Docker

prepare folder for db:

```bash
cd C:\\Dev\\Learning\\ai\\week1
mkdir -p qdrant_storage
```

## run qdrant

```bash windows
docker run -d --name qdrant -p 6333:6333 -p 6334:6334 -v D:\\qdrant_storage:/qdrant/storage qdrant/qdrant
```

```bash wsl
docker run -d --name qdrant -p 6333:6333 -p 6334:6334 -v /mnt/d/qdrant_storage:/qdrant/storage qdrant/qdrant
```

# 2 Python 3.12

Yes — that explains the `apt` error. You're on **Ubuntu 26.04 LTS (Resolute)**, whose default Python is **3.14**, so `python3.12` isn't in the standard repository.

More importantly, I would **not downgrade the system Python**. Keep Ubuntu's Python 3.14 and install Python 3.12 alongside it.

### Recommended approach: `pyenv`

Run this inside WSL:

```bash
sudo apt update

sudo apt install -y \
  build-essential \
  curl \
  git \
  libssl-dev \
  zlib1g-dev \
  libbz2-dev \
  libreadline-dev \
  libsqlite3-dev \
  libncursesw5-dev \
  xz-utils \
  tk-dev \
  libxml2-dev \
  libxmlsec1-dev \
  libffi-dev \
  liblzma-dev \
  libgdbm-dev \
  libnss3-dev
```

Install `pyenv`:

```bash
curl https://pyenv.run | bash
```

Then add it to your shell:

```bash
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init - bash)"' >> ~/.bashrc

source ~/.bashrc
```

Verify:

```bash
pyenv --version
```

Then install Python 3.12:

```bash
pyenv install 3.12.11
```

Set it for your project:

```bash
cd /mnt/c/Dev/Learning/ai/week1

pyenv local 3.12.11

python --version
```

You should now see:

```text
Python 3.12.11
```

### Recreate your venv

Since your existing venv was created with Python 3.14, recreate it:

```bash
deactivate 2>/dev/null || true

rm -rf venv

python -m venv venv
source venv/bin/activate

python --version
```

Then:

```bash
python -m pip install --upgrade pip setuptools wheel
```

---

### But let's fix the original Triton problem properly

Changing Python versions may solve it, but I don't want you to rebuild everything only to discover that the actual problem is `libcuda.so.1`.

Before reinstalling vLLM, run these **four commands**:

```bash
gcc --version
```

```bash
ls -l /usr/lib/wsl/lib/libcuda.so.1
```

```bash
nvidia-smi
```

```bash
python -c "import torch; print('PyTorch:', torch.__version__); print('CUDA:', torch.version.cuda); print('Available:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NONE')"
```

Also, because the original error is specifically a GCC compilation failure, **please paste the lines immediately before**:

```text
returned non-zero exit status 1
```

For example, if GCC says:

```text
/usr/bin/ld: cannot find -l:libcuda.so.1
```

then Python 3.12 won't fix the underlying problem—we need to fix WSL's CUDA library path.

If you have the complete traceback as a text file, you can upload it here and I can inspect the exact GCC failure:

## Image to text OCR

pip install easyocr pdf2image pytesseract pillow

### Also need poppler (for pdf2image):

### Ubuntu: sudo apt-get install poppler-utils

### Mac: brew install poppler

### Windows: download from https://github.com/oschwartz10612/poppler-windows/releases/
