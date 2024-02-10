if [ -n "${BASH_SOURCE-}" ]; then
    script_path="${BASH_SOURCE}"
elif [ -n "${ZSH_VERSION-}" ]; then
    script_path="${(%):-%x}"
else
    script_path=$0
fi
script_dir=$(dirname $(realpath $script_path))

PY_VENV_PATH=${script_dir}/venv
if [[ ! -d "$PY_VENV_PATH" ]]; then
    source ${script_dir}/bootstrap.sh
fi
source ${PY_VENV_PATH}/bin/activate
