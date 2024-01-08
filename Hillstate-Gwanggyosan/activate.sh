script_path=$(dirname $(realpath $0))
PY_VENV_PATH=${script_path}/venv
if [[ ! -d "$PY_VENV_PATH" ]]; then
    source ${script_path}/bootstrap.sh
fi
source ${PY_VENV_PATH}/bin/activate
