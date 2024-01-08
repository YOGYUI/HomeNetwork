script_path=$(dirname $(realpath $0))

# create python virtual environment
PY_VENV_PATH=${script_path}/venv
python -m venv ${PY_VENV_PATH}

# activate virtual environment 
source ${PY_VENV_PATH}/bin/activate

# install python packages
pip install -r ${script_path}/requirements.txt
