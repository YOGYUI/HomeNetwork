from . import api
from flask import render_template, jsonify
from flask_wtf import FlaskForm
from wtforms import FloatField, TextAreaField, BooleanField
import os
import sys
CURPATH = os.path.dirname(os.path.abspath(__file__))  # /project/web/api/
PROJPATH = os.path.dirname(os.path.dirname(CURPATH))  # /project/
INCPATH = os.path.join(PROJPATH, 'Include')  # /project/Include
sys.path.extend([CURPATH, PROJPATH, INCPATH])
sys.path = list(set(sys.path))
from Include import get_home


class OutletStatusForm(FlaskForm):
    about_me = TextAreaField('About me')
    confirmed = BooleanField('Confirmed')
    field_1_1 = FloatField(f"Outlet {1}", validators=[], render_kw={"disabled": "disabled"},
                           id=f"outlet_{1}_{1}")
    field_1_2 = FloatField(f"Outlet {2}", validators=[], render_kw={"disabled": "disabled"},
                           id=f"outlet_{1}_{2}")
    field_1_3 = FloatField(f"Outlet {3}", validators=[], render_kw={"disabled": "disabled"},
                           id=f"outlet_{1}_{3}")

    field_2_1 = FloatField(f"Outlet {1}", validators=[], render_kw={"disabled": "disabled"},
                           id=f"outlet_{2}_{1}")
    field_2_2 = FloatField(f"Outlet {2}", validators=[], render_kw={"disabled": "disabled"},
                           id=f"outlet_{2}_{2}")

    field_3_1 = FloatField(f"Outlet {1}", validators=[], render_kw={"disabled": "disabled"},
                           id=f"outlet_{3}_{1}")
    field_3_2 = FloatField(f"Outlet {2}", validators=[], render_kw={"disabled": "disabled"},
                           id=f"outlet_{3}_{2}")


@api.route('/outlet_info', methods=['GET', 'POST'])
def outlet_info():
    form = OutletStatusForm()
    return render_template('outlet.html', form=form)


@api.route('/outlet_info/update', methods=['POST'])
def outlet_update():
    home = get_home()
    data = dict()
    for room in home.rooms:
        idx = room.index
        for i, o in enumerate(room.outlets):
            data[f'room{idx}_outlet{i + 1}'] = o.measurement
    return jsonify(data)
