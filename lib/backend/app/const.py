import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

DEBUG = True 

CFG_PATH = "/opt/sat/conf/sar-index.cfg"
#CFG_PATH = "/home/calix/sat/lib/backend/conf/sar-index.cfg"

LOG_FILENAME = 'sat_app.log'

LOG_FILESIZE = 100000 # in Bytes

SA_DIR = 'safiles'

# Use a secure, unique and absolutely secret key for
# signing the data.
#CSRF_SESSION_KEY = "*@^@^%^*THD66GDFCVWRB%heafidpxry02%%"

# Secret key for signing cookies
SECRET_KEY = "#$JATFGYTE^$TFEFV#$%$&"

# Dictionary that holds all the template configuration
TEMPLATE_CONFIGURATION = { 
    # The title of the application as shown by the browser
    "header_text" : "Sar Analytics Tool v.1.0",
    "help_text" : "upload SA binary file (from /var/log/sa/) here",
    "placeholder" : "/var/log/sa/saYYYYMMDD. YYYY stands for the current year, MM for the current month and DD for the current day"
}

HOST = "0.0.0.0"
PORT = 8000

USER = 'admin'
PASSWORD = 'admin'
