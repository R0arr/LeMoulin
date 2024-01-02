#from unidecode import unidecode
import os
#import hmac
#import hashlib
from functools import wraps
from flask import redirect, render_template, session

weekdays = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]

def generate_csrf_token():
    if '_csrf_token' not in session:
        # Generate CSRF token using HMAC and the global secret key
        # csrf_token = hmac.new(app.secret_key, os.urandom(24), hashlib.sha256).hexdigest()
        csrf_token = os.urandom(24).hex()
        session['_csrf_token'] = csrf_token
    return session['_csrf_token']

def to_title(string):
    string.title()
    return string

def login_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user_id') is None:
            return redirect('/connexion')        
        return f(*args, **kwargs)
        
    return decorated_function

def redirect_bakers(f):
    @wraps(f)
    def decorated_function(*args,**kwargs):
        if session.get('type') == "baker":
            return redirect('/compte-pro')
        return f(*args, **kwargs)
    return decorated_function


def custom_collate(str1:str, str2:str):
    str1 = unidecode(str1,'ignore').casefold()   
    str2 = unidecode(str2,'ignore').casefold()  
    return 0 if str1 == str2 else - 1

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def currency_format(number):    
    if not number:
        number = 0

    if isinstance(number, str):  
             
        if '€' in number:            
            number = number.strip('€')  
        if ',' in number:            
            number = number.replace(',', '.')        
                          
        number = float(number) 

    number = f"{number:,.2f}€"       
   
    return number
    

def loc_day_name(number):
    name = weekdays[number]
    return name

def reg_type(type):
    if type == "weekly":
        name = "1 fois par semaine"
        return name

def create_folder(name, id):
    root_path = os.path.dirname(os.path.abspath(__file__))
    orders_path = os.path.join(root_path, 'orders')
    folder_path = os.path.join(orders_path, f'{name}_{id}')

    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    
    else:
        files = os.listdir(folder_path)

        for file in files:
            file_path  = os.path.join(folder_path, file)
            if os.path.isfile(file_path):
                os.remove(file_path)    
                        
    return folder_path




    








        
    

    






