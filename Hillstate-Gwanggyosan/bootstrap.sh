script_dir=$(dirname $(realpath $"0"))

# create python virtual environment
PY_VENV_PATH=${script_dir}/venv
python3 -m venv ${PY_VENV_PATH}

# activate virtual environment 
source ${PY_VENV_PATH}/bin/activate

# install python packages
pip install -r ${script_dir}/requirements.txt
