script_dir=$(dirname $(realpath $"0"))
PY_VENV_PATH=${script_dir}/venv
if [[ ! -d "$PY_VENV_PATH" ]]; then
    source ${script_dir}/bootstrap.sh
fi
source ${PY_VENV_PATH}/bin/activate
