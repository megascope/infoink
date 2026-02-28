if [ $# -ne 1 ]; then
    echo "Usage: $0 <target_directory/host>"
    exit 1
fi
TARGET=$1

set -x
rsync -aviP \
  --exclude .venv \
  --exclude .git \
  --exclude __pycache__ \
  . ${TARGET}
