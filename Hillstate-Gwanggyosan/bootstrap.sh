if [ -n "${BASH_SOURCE-}" ]; then
    script_path="${BASH_SOURCE}"
elif [ -n "${ZSH_VERSION-}" ]; then
    script_path="${(%):-%x}"
else
    script_path=$0
fi
script_dir=$(dirname $(realpath $script_path))

# create python virtual environment
PY_VENV_PATH=${script_dir}/venv
python3 -m venv ${PY_VENV_PATH}

# activate virtual environment 
source ${PY_VENV_PATH}/bin/activate

# install python packages
pip install --upgrade pip
pip install --no-cache-dir -r ${script_dir}/requirements.txt
