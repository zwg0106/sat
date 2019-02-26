import os
import json
from flask_wtf import Form, RecaptchaField
from wtforms import TextField, \
  PasswordField, \
  BooleanField, \
  SelectMultipleField, \
  SelectField, \
  StringField, \
  TextAreaField, \
  FileField
from wtforms.validators import Required, EqualTo, Email

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
SAR_ARGS = os.path.join(BASE_DIR, 'static/sar_args_mapping.json')
SAR_MODES = json.load(open(SAR_ARGS, 'r'))
SINGLE_MODE = list(enumerate(SAR_MODES['single'], start=1))

class LoginForm(Form):
    username = StringField('Username', [Required()])
    password = PasswordField('Password', [Required()])

class RegisterForm(Form):
    name = TextField('NickName', [Required()])
    email = TextField('Email address', [Required(), Email()])
    password = PasswordField('Password', [Required()])
    confirm = PasswordField('Repeat Password', [
                            Required(),
                            EqualTo('password', message='Passwords must match')
                            ])
    accept_tos = BooleanField('I accept the TOS', [Required()])
    recaptcha = RecaptchaField()

class UploadForm(Form):
    check_all = BooleanField()
    cmd_mode = BooleanField(default=False)
    datafile = FileField([Required()])
    graph_types = SelectMultipleField(choices=SINGLE_MODE, coerce=int)
