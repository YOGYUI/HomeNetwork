from . import api
from flask import render_template
import os
import sys
CURPATH = os.path.dirname(os.path.abspath(__file__))  # {$PROJECT}/web/api/
PROJPATH = os.path.dirname(os.path.dirname(CURPATH))  # {$PROJECT}/
INCPATH = os.path.join(PROJPATH, 'Include')  # {$PROJECT}/Include/
sys.path.extend([CURPATH, PROJPATH, INCPATH])
sys.path = list(set(sys.path))
del CURPATH, PROJPATH, INCPATH
from Include import get_home


@api.route('/restart', methods=['GET', 'POST'])
def restart():
    home = get_home()
    home.restart()
    return render_template('index.html')