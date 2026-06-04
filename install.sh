#!/usr/bin/env bash
# Install dependencies for DB2 Multi-DB Object Explorer.
# On Apple Silicon macOS with system Python, ibm_db needs Python.h via CFLAGS.

set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

pip install --upgrade pip
pip install streamlit pandas

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_INCLUDE=$(python3 -c "import sysconfig, os; print(os.path.join(sysconfig.get_path('include')))")

if [[ "$(uname -s)" == "Darwin" && "$(uname -m)" == "arm64" ]]; then
  if [[ ! -f "${PY_INCLUDE}/Python.h" ]]; then
    echo "Python.h not found at ${PY_INCLUDE}"
    echo "Install Xcode Command Line Tools:  xcode-select --install"
    exit 1
  fi
  echo "Apple Silicon detected — installing ibm_db with CFLAGS for Python.h"
  export CFLAGS="-I${PY_INCLUDE}"
fi

pip install ibm_db

echo ""
echo "Done. Run:  source .venv/bin/activate && streamlit run app.py"
