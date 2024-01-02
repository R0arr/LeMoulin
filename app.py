from flask import Flask, render_template, request, flash, jsonify, redirect, session
import os

import requests
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
import re
from helpers import (custom_collate, dict_factory,currency_format, create_folder, weekdays, loc_day_name, reg_type, to_title,
                     login_required, redirect_bakers, generate_csrf_token)
import sqlite3
from datetime import datetime, timedelta, time
import locale
from dotenv import load_dotenv
#from reportlab.lib.pagesizes import C10, A5
#from reportlab.platypus import SimpleDocTemplate, PageBreak, Spacer, Paragraph, Table, TableStyle
#from reportlab.lib.styles import getSampleStyleSheet
#from reportlab.lib.units import mm

import time
import threading
import csv

#configure application
app = Flask(__name__)

#configure Jinja templates filters
app.jinja_env.filters['eur'] = currency_format
app.jinja_env.filters['day_name'] = loc_day_name
app.jinja_env.filters['order_type'] = reg_type
app.jinja_env.filters['title'] = to_title

#templates auto reload
app.config['TEMPLATES_AUTO_RELOAD'] = True

#load variables from .env file
load_dotenv()

#configure Secret Key
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')

#configure Recaptcha Secret Key
app.config['RECAPTCHA_SECRET_KEY'] = os.environ.get('RECAPTCHA_SECRET_KEY')

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=60)
app.config["SESSION_TYPE"] = "filesystem"
Session(app)



# Ensure browser isn't caching anything
app.after_request
def after_request(response):
    response.headers['Cache-control'] = "no-cache, no-store, must-revalidate" 
    response.headers['Expires'] = 0
    response.headers['Pragma'] = 'no-cache'
    return response

#set french local settings

locale.setlocale(locale.LC_ALL, "fr_FR")

LOGIN_ATTEMTPTS = {}


@app.route("/")
@redirect_bakers
@login_required
def index():
   
    message = "Commander en Ligne" 
    return render_template("index.html", message=message)
    

@app.route("/connexion", methods=["GET", "POST"])
def connexion():

    session.clear() 
    ip_adress = request.remote_addr  
    recaptcha = '<div class="g-recaptcha" data-sitekey="6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI"></div>'   


    if request.method == "POST":

        conn = sqlite3.connect('moulin.db')
        conn.row_factory = dict_factory
        db = conn.cursor()
        email = request.form.get("email").lower()
        password = request.form.get("password")
        

        if not email or not password:
            message = "Entrer un email et mot de passe svp"   
            if LOGIN_ATTEMTPTS.get(ip_adress, 0) >=3: 
                return render_template("connexion.html", message=message, recaptcha=recaptcha)
            else:       
                return render_template("connexion.html", message=message)
        
        try:
            user_data = db.execute("SELECT * FROM users WHERE mail = ?", (email,)).fetchall()
           
            if len(user_data) != 1 or user_data[0]['mail'] != email or not check_password_hash(user_data[0]['hash'],password):

                LOGIN_ATTEMTPTS[ip_adress] = LOGIN_ATTEMTPTS.get(ip_adress, 0) + 1                
                message = "Email ou mot de passe non valide"               

                if LOGIN_ATTEMTPTS.get(ip_adress, 0) >= 3 :                   
                    return render_template("connexion.html", message=message, email=email, recaptcha=recaptcha)
                else:                    
                    return render_template("connexion.html", message=message, email=email)                
        
            else:

                if LOGIN_ATTEMTPTS.get(ip_adress, 0) >= 3 :
                    recaptcha_response = request.form['g-recaptcha-response']

                    if not recaptcha_response:
                        message = "Remplir le test recaptcha svp"
                        return render_template('connexion.html', message=message, email=email, recaptcha=recaptcha)
                    
                    data = {
                    'secret': app.config['RECAPTCHA_SECRET_KEY'],
                    'response': recaptcha_response
                    }

                    response = requests.post('https://www.google.com/recaptcha/api/siteverify', data=data)
                    result = response.json()
                    print(result)
                    if result['success']:
                        LOGIN_ATTEMTPTS.pop(ip_adress)
                        session['user_id'] = user_data[0]['id']
                        session['name'] = user_data[0]['name'] 
                        session['type'] = user_data[0]['type'] 
                        return redirect("/")
                    else:
                        message = "Echec de la vérification, recommencez svp"
                        return render_template('connexion.html', email=email, message=message, recaptcha=recaptcha)
                    
                session['user_id'] = user_data[0]['id']
                session['name'] = user_data[0]['name'] 
                session['type'] = user_data[0]['type'] 
                return redirect("/")
                
            
        finally:
            db.close()
            conn.close()
    

    if LOGIN_ATTEMTPTS.get(ip_adress, 0) < 3:
        return render_template("connexion.html")
    else:        
        return render_template("connexion.html", recaptcha=recaptcha)


@app.route("/deconnexion")
def deconnexion():

    session.clear()
    return redirect("/")        

    

@app.route("/inscription", methods=["GET", "POST"])
def inscription():

    if request.method == "POST":

        conn = sqlite3.connect('moulin.db')
        conn.row_factory = dict_factory
        db = conn.cursor()

        email = request.form.get("email").lower() 
        email_confirmation = request.form.get("email_confirmation").lower() 
        name = request.form.get("name").title()        
        password = request.form.get("password")
        confirmation = request.form.get("confirmation") 
        phone =  request.form.get("phone")
        baker = request.form.get("is-baker")
        print(baker)

        email_template = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        password_template = r'^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[@#$%^&+=!]).*$'    

                
        if not email or not email_confirmation or not password or not confirmation or not phone or not name:
            message = "Entrez un email, nom, mot de passe et numéro de téléphone"
            return render_template("inscription.html", message=message, email=email, email_confirmation=email_confirmation, name=name, password=password, confirmation=confirmation, phone=phone)
        
        elif email != email_confirmation:
            message = "Vérifiez votre email"
            return render_template("inscription.html", message=message, email=email, email_confirmation=email_confirmation, name=name, password=password, confirmation=confirmation, phone=phone)
        
        elif password != confirmation:
            message = "Les mots de passe ne correspondent pas"
            return render_template("inscription.html", message=message, email=email, email_confirmation=email_confirmation, name=name, password=password, confirmation=confirmation, phone=phone)
        
        elif len(phone) != 10 or not phone.isdigit:
            message = "Entrez un numéro de téléphone valide"
            return render_template("inscription.html", message=message, email=email, email_confirmation=email_confirmation, name=name, password=password, confirmation=confirmation, phone=phone)
        
        elif not re.match(email_template, email) or not re.match(email_template, email_confirmation):
            message = "Votre email n'est pas correct"
            return render_template("inscription.html", message=message, email=email, email_confirmation=email_confirmation, name=name, password=password, confirmation=confirmation, phone=phone)
        
        elif not re.match(password_template, password) or not re.match(password_template, confirmation):
            message = "Votre mot de passe doit contenir : minuscule, majuscule, chiffre et caractère spécial"
            return render_template("inscription.html", message=message, email=email, email_confirmation=email_confirmation, name=name, password=password, confirmation=confirmation, phone=phone)
        
        hash = generate_password_hash(password)
        country = "France"

        if baker:
            type= "baker"
        else:
            type = "user"

        try: 
            rows=db.execute("SELECT mail FROM users")

            for row in rows:
                if row['mail'] == email:
                    message = "Cet email est déjà utilisé"
                    return render_template("inscription.html", message=message, email=email, email_confirmation=email_confirmation, name=name, password=password, confirmation=confirmation, phone=phone)


            db.execute("INSERT INTO users (mail, name, hash, phone, country,type) VALUES(?,?,?,?,?,?)", (email, name, hash, phone, country, type))
            conn.commit()    

            return redirect("/connexion")
        
        finally:
            db.close()
            conn.close()         

    return render_template("inscription.html")


@app.route("/recherche") 
def recherche():

    conn = sqlite3.connect('moulin.db')
    conn.row_factory = dict_factory
    # conn.create_collation('custom', custom_collate)
    db = conn.cursor()

    bakery = request.args.get("bakery")   
    
    try:  

        if bakery:
            bakeries = db.execute("SELECT * FROM bakeries WHERE name LIKE ? OR city LIKE ? LIMIT 10", ("%" + bakery + "%" , "%" + bakery + "%")).fetchall()
            
        else:
            bakeries = []
    
        return render_template("recherche.html", bakeries=bakeries)
    
    finally :
        db.close()
        conn.close()


@app.route("/boulangerie")
def boulangerie():

    conn = sqlite3.connect('moulin.db')
    conn.row_factory = dict_factory    
    db = conn.cursor()

    if request.method == "GET":

        bakery_id = request.args.get("bakery_id") 

        try:   

            bakery_row = db.execute("SELECT * FROM bakeries WHERE id = ?", bakery_id).fetchall()
            bakery = bakery_row[0]
            menu_cat = db.execute("SELECT cat FROM menu WHERE bakery_id = ? GROUP BY cat", (bakery['id'],)).fetchall()
            menu = db.execute("SELECT * FROM menu WHERE bakery_id = ?", (bakery['id'],)).fetchall()

            return render_template("boulangerie.html", bakery=bakery, menu_cat=menu_cat, menu=menu)
        
        finally:
            db.close()
            conn.close()


@app.route("/get_menu")
def get_menu():

    user_id = session['user_id']
    item = request.args.get("item")

    conn = sqlite3.connect('moulin.db')
    conn.row_factory = dict_factory    
    db = conn.cursor()

    try: 
        if item:

            if len(item) > 3:
                bakery = db.execute("SELECT * FROM bakeries WHERE owner = ?", (user_id,)).fetchone()        
                menu = db.execute("SELECT * FROM menu WHERE bakery_id = ? AND name LIKE ?", (bakery['id'], "%" + item + "%")).fetchall()            

                return jsonify(menu, bakery['id']) 
            
          
        bakery = db.execute("SELECT * FROM bakeries WHERE owner = ?", (user_id,)).fetchone()        
        menu = db.execute("SELECT * FROM menu WHERE bakery_id = ?", (bakery['id'],)).fetchall()  

        return menu    
    
    finally:
        conn.commit()
        db.close()
        conn.close()



@app.route("/commande")
def commande():
    

    return render_template("commande.html")



@app.route('/update_cart', methods=['POST'])
def update_cart():

    data = request.get_json()    

    if request.headers.get("X-type") == 'order_items':       

        session['order'] = data

        return jsonify({ "message" : "cart updated" })
    
    if request.headers.get("X-type") == 'order_date': 

        submitted_token = data[3]
        session_token = session.pop('_csrf_token', None)

        if not submitted_token or not session_token or submitted_token != session_token:   
            session.clear()
            return jsonify("session has been cleared")
        
        else:     
        
            session['order_date'] = data[0]
            session['order_type'] = data[1]
            session['note'] = data[2]        

            return jsonify({ "message" : "cart updated" })
    

@app.route("/rdv", methods=['GET', 'POST'])
def rdv():

    if request.method == 'GET':

        csrf_token = generate_csrf_token()

        conn = sqlite3.connect('moulin.db')
        conn.row_factory = dict_factory    
        db = conn.cursor()    

        try:

            bakery_id = request.args.get("bakery_id")
            session['bakery'] = bakery_id 

            if bakery_id:

                bakery_row = db.execute("SELECT * FROM bakeries WHERE id = ?", bakery_id).fetchall()
                bakery = bakery_row[0]        

            else:
                bakery=[]
            
        finally:
            db.close()
            conn.close()
        
        return render_template("rdv.html",bakery=bakery, csrf_token=csrf_token)
    
    data = request.get_json()
    



@app.route("/confirmation")
@login_required
def confirmation():    
    order = session['order']    
    order_date = session['order_date']
    order_date = datetime.strptime(order_date,'%Y-%m-%dT%H:%M:%S.%fZ')    
    order_day = order_date.weekday()
    order_type = session['order_type']   
    user_id = session['user_id']
    note = session['note']
    user_type = session['type']    

    if order:
        conn= sqlite3.connect('moulin.db')
        conn.row_factory = dict_factory
        db = conn.cursor()

        try:

            if order_type == "":
                is_regular = 0
                order_frequency = 1
            elif order_type == "weekly":
                is_regular = 1
                order_frequency = 5
                delta_days = 7

            next_id = None             
            ref_order = []

            if user_type == "user":
                if is_regular:

                        reg_orders = db.execute("""SELECT
                                                    ref_day                                          
                                                    FROM orders_reg                                                   
                                                    WHERE user_id = ?
                                                """, (user_id,)).fetchall()
                            
                        for reg_order in reg_orders:
                            if reg_order['ref_day'] == order_day:
                                alert = "Vous avez déjà une commande régulière les " + weekdays[order_day] + "s" 
                                bakery = int(session['bakery'])
                                
                                return render_template("confirmation.html", alert=alert, bakery=bakery)          

            for i in range(order_frequency):                
                        
                next_date = order_date + timedelta(days=7*i) 
                next_date = next_date.strftime("%Y-%m-%dT00:00:00.000Z")     

                db.execute("INSERT INTO orders (order_date, user_id, note, status) VALUES (?,?,?,?)", (next_date, user_id, note, 1))  
                conn.commit()
                
                last_id = db.execute("SELECT MAX(id) AS id FROM orders WHERE user_id = ?", (user_id,)).fetchone()              
                last_id = last_id['id']        
                total_order = 0
                if i == 0:
                    next_id = last_id

                for item in order:
                    item_id = item['id']
                    item_qty = item['qty']
                    item_price = item['price']
                    total_price = item_qty * item_price 
                    total_order += total_price         
                
                    db.execute("INSERT INTO order_items (order_id, item_id, item_qty, item_price, total_price) VALUES (?,?,?,?,?)", 
                            (last_id, item_id, item_qty, item_price, total_price))  
                    

                if order_type:  
                    db.execute("UPDATE orders SET total_order = ?, ref_order = ? WHERE id = ?", (total_order, next_id, last_id)) 
                else:
                    db.execute("UPDATE orders SET total_order = ? WHERE id = ?", (total_order, last_id))   

                if i == 0:
                    total = total_order           

            if is_regular:
                check_date = order_date + timedelta(days=delta_days)                
                check_date = check_date.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                is_active = 1
                
                db.execute("INSERT INTO orders_reg (ref_order, type, checkdate, status, user_id, ref_day ) VALUES (?,?,?,?,?,?)", (next_id, order_type, check_date, is_active, user_id, order_day))

            ref_order = db.execute("""SELECT name, item_qty, item_price, total_price 
                                            FROM order_items                                           
                                            JOIN menu ON menu.id = item_id 
                                            WHERE order_id = ?
                                     """,(next_id,)).fetchall()

            session['order'] = None
            session['order_date'] = None
            session['order_type'] = None      


        finally:
            conn.commit()
            db.close()
            conn.close()  

        return render_template('confirmation.html', order=ref_order, total=total, date=order_date.strftime("%A %d %B %Y").title())        

    else:
        return redirect("/")

@app.route("/compte")
@login_required
def compte():

    user_type = session['type'] 

    if user_type == "baker":
        return redirect("/compte-pro")
    
    conn = sqlite3.connect('moulin.db')
    conn.row_factory = dict_factory
    db = conn.cursor()
    
    user_id = session['user_id']

    try: 
        user_data = db.execute("SELECT name FROM users WHERE id = ? ", (user_id,)).fetchone()
        user_name = user_data['name']      
   
        return render_template("compte.html", name=user_name)

    finally:
        conn.commit()
        db.close()
        conn.close()




@app.route("/compte/commandes")
@login_required
def compte_commandes():        

    csrf_token = generate_csrf_token()        
    user_id = session['user_id']
            

      
    
    conn = sqlite3.connect("moulin.db")
    conn.row_factory = dict_factory
    db = conn.cursor()

    try:          
            
        reg_orders = db.execute(""" SELECT                                              
                                    orders_reg.ref_order, 
                                    orders_reg.status,
                                    ref_day,
                                    type,
                                    total_order                                        
                                    FROM orders_reg
                                    JOIN orders ON orders.id = orders_reg.ref_order                                        
                                    WHERE orders_reg.user_id = ?                           
                                """, (user_id,)).fetchall()
        
        reg_orders_items = db.execute(""" SELECT
                                            ref_order,  
                                            name,
                                            item_qty,
                                            item_price                                               
                                            FROM orders_reg
                                            JOIN order_items ON order_id = ref_order 
                                            JOIN menu ON menu.id = item_id                                              
                                            WHERE user_id = ?    
                                        """, (user_id,)).fetchall()
        
        
        for order in reg_orders:
            order['list'] = []                    
            for item in reg_orders_items:
                if item['ref_order'] == order['ref_order']:
                    order['list'].append(item)
        

        return render_template("compte-commandes.html", reg_orders=reg_orders, csrf_token=csrf_token)

    finally:
        conn.commit()
        db.close()
        conn.close()  



@app.route("/compte-pro")
def compte_pro():
    conn = sqlite3.connect('moulin.db')
    conn.row_factory = dict_factory
    db = conn.cursor()
    
    user_id = session['user_id']

    try: 
        bakery = db.execute("SELECT name FROM bakeries WHERE owner = ? ", (user_id,)).fetchone()
        bakery_name = bakery['name']      
   
        return render_template("compte-pro.html", name=bakery_name)

    finally:
        conn.commit()
        db.close()
        conn.close()            
        

@app.route("/compte-pro/commandes", methods=['GET', 'POST'])

def compte_pro_commandes():

    csrf_token = generate_csrf_token()
    today = datetime.now().date()

    if request.method == "GET": 
              
        return render_template("compte-pro-commandes.html", today=today)
    
    date = request.form.get("date")    

    if not date:
        message = "Entrez une date"
        return render_template("compte-pro-commandes.html", today=today, message=message)
    
    data = orders(date)
    data = data.get_json()
    day_orders = data[0]
    categories = []
    summary = data[1]
    message = None

    if not day_orders:
        message="Pas de commande ce jour"   
    
    
    for line in summary:
        if line['cat'] not in categories:
            categories.append(line['cat'])   


    return render_template("compte-pro-commandes.html", today=today, message=message, date=date, orders=day_orders, summary=summary, categories=categories, csrf_token=csrf_token)


    
    





    """csrf_token = generate_csrf_token()

    today = datetime.now().date()
    tomorrow = today + timedelta(hours=24)
    after_tomorrow = today + timedelta(hours=48)
    today_plus_3 = today + timedelta(hours=72)
    today_plus_4 = today + timedelta(hours=96)
    today_plus_5 = today + timedelta(hours=120)
    today_plus_6 = today + timedelta(hours=144)

    next_week = [str(today), str(tomorrow), str(after_tomorrow),str(today_plus_3), str(today_plus_4), str(today_plus_5), str(today_plus_6)]    

    today_str = weekdays[today.weekday()]   
    tomorrow_str = weekdays[tomorrow.weekday()]  
    after_tomorrow_str = weekdays[after_tomorrow.weekday()]  
    today_plus_3_str = weekdays[today_plus_3.weekday()]  
    today_plus_4_str = weekdays[today_plus_4.weekday()]  
    today_plus_5_str = weekdays[today_plus_5.weekday()] 
    today_plus_6_str = weekdays[today_plus_6.weekday()]  

    next_week_str = [today_str, tomorrow_str, after_tomorrow_str, today_plus_3_str, today_plus_4_str, today_plus_5_str, today_plus_6_str]  

    conn = sqlite3.connect('moulin.db')
    conn.row_factory = dict_factory
    db = conn.cursor()
    
    user_id = session['user_id']

    try: 
        bakery = db.execute("SELECT name FROM bakeries WHERE owner = ? ", (user_id,)).fetchone()
        bakery_name = bakery['name']      
   
        return render_template("compte-pro-commandes.html", next_week=next_week, next_week_str=next_week_str, name=bakery_name, csrf_token=csrf_token)

    finally:
        conn.commit()
        db.close()
        conn.close()"""


@app.route('/compte-pro/profil', methods=['GET', 'POST'])
def compte_pro_profil():

    user_id = session['user_id']  

    if request.method == 'GET':

        conn = sqlite3.connect('moulin.db')
        conn.row_factory = dict_factory
        db = conn.cursor()           

        try:
            user_data = db.execute("SELECT name, mail, phone FROM users WHERE id = ?", (user_id,)).fetchone()           
            return render_template('compte-pro-profil.html', user=user_data)

        finally:
            db.close()
            conn.commit()    
            conn.close()

    else:

        data = request.form.to_dict()      
        mail = data['mail']
        password = data['password']
        phone = data['phone']      

        email_template = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        password_template = r'^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[@#$%^&+=!]).*$'
        is_error = False

        messages = {"mail" : "Vérifier votre email", "phone" : "Votre numéro est incorrect" , "password": "Votre mot de passe doit contenir minuscule, majuscule, chiffre et caractère spécial"}
        
        if not re.match(email_template, mail):
            flash(messages['mail'], 'mail')
            is_error = True
        if password:
            if not re.match(password_template, password):
                flash(messages['password'], 'password')
                is_error = True
            else: 
                password = generate_password_hash(password)
                data['hash'] = password
                data.pop('password')
        if not len(phone) == 10 or not phone.isdigit():
            flash(messages['phone'], 'phone')
            is_error = True

        if is_error:
            return render_template('compte-pro-profil.html', user=data)

        conn = sqlite3.connect('moulin.db')
        conn.row_factory = dict_factory
        db = conn.cursor()             

        try:
            user_data = db.execute("SELECT name, mail, phone, hash FROM users WHERE id = ?", (user_id,)).fetchone() 
            is_updated = 0
            for key in data:                   
                if not data[key]: 
                    continue
                if data[key] == user_data[key]:
                    pass   
                else: 
                    is_updated +=1
                    db.execute(f"UPDATE users SET {key} = ? WHERE id = ?", (data[key], user_id))

            if is_updated > 0: flash('Profil mis à jour', 'updated') 

            return redirect('/compte-pro/profil')

        finally:
            db.close()
            conn.commit()    
            conn.close()



@app.route('/compte-pro/menu', methods=['GET', 'POST'])
def compte_pro_menu():

    menu = get_menu()   
    categories = [] 
  

    for item in menu:
        if item['cat'] not in categories:
            categories.append(item['cat'])                        

    if request.method == "GET":  

        return render_template("compte-pro-menu.html", menu=menu, categories=categories)
    
    data = request.form.to_dict()  
    data_ok = True   
    delete_items = []
    same_items = []
    
    for item in data:
        pattern = r'^(?!0)\d+([\.\,]\d{1,2})?€?$' 
        message = None
        
         
        if data[item] != 'on':

            if not re.match(pattern, data[item]):
                message = "Entrez un nombre (ex: 1.00 ou 1)"                       
                data_ok = False   

        else :
            delete_items.append(int(item.strip('del-')))              

        for list_item in menu: 
            print(item,data[item],list_item['price'])           
            if item == list_item['name']:  
                if data[item].strip('€') == f'{list_item["price"]:,.2f}':
                    same_items.append(menu.pop(menu.index(list_item)))
                    continue                          
                list_item['price'] = data[item]                    
                list_item['message'] = message
                break
                


    if not data_ok:

        for item in same_items:
            menu.append(item)
        print("Delete:",delete_items ,"\nSame:",same_items)
        return render_template("compte-pro-menu.html", menu=menu, categories=categories, deleted=delete_items)  


    conn = sqlite3.connect('moulin.db')
    conn.row_factory = dict_factory
    db = conn.cursor()
    
    try:     
        for item in menu:    
                  
                item.pop('message')               
                item['price'] = item['price'].strip('€').replace(',','.')     
                item['price'] = float(item['price'])               
                db.execute('UPDATE menu SET price = ? WHERE id = ?', (item['price'], item['id']))

    finally : 
        db.close()
        conn.commit()
        conn.close()

    flash("Menu mis à jour")
    
    return redirect('/compte-pro/menu')

    

    




@app.route("/orders", methods=['GET'])
def orders(order_date=None):

    user_id = session['user_id']
    user_type = session['type']

    conn = sqlite3.connect("moulin.db")
    conn.row_factory = dict_factory
    db = conn.cursor() 

    date = request.args.get("date")  
    if order_date:
        date = order_date
    
   
    try: 

        if user_type == "baker":
            user = db.execute("SELECT id,name FROM bakeries WHERE owner = ?", (user_id,)).fetchone()
            user_template = "bakery_id"
            user_id = user['id']            
        
        else: 
            user = db.execute("SELECT name, mail, phone FROM users WHERE id = ?", (user_id,)).fetchone()
            user_template = "user_id"   

        if date:  
            extra_query = "AND date(order_date) = ? "      
            args = (user_id, date)

        else:   
            extra_query = ""   
            args = (user_id,)              
        
        query_orders = f""" SELECT 
                                    strftime('%d/%m/%Y', order_date) AS date,
                                    date(order_date) AS num_date, 
                                    CASE
                                        WHEN date(order_date) <  date('now')THEN "true"
                                        WHEN order_date IS NULL THEN "true"
                                        ELSE "false"
                                    END AS archive,  
                                    CASE
                                        WHEN ref_order IS NOT NULL THEN 1
                                        ELSE 0
                                    END AS is_regular,                                   
                                    orders.id,    
                                    total_order, 
                                    note,                      
                                    users.name,
                                    bakeries.name AS bakery_name                                                                      
                                    FROM orders
                                    JOIN order_items ON orders.id = order_id
                                    JOIN users ON users.id = user_id
                                    JOIN menu ON menu.id = item_id
                                    JOIN bakeries ON bakery_id = bakeries.id
                                    WHERE {user_template} = ? {extra_query} AND status = 1
                                    GROUP BY orders.id                                           
                                    ORDER BY num_date DESC                                                                       
                        """
        
        orders = db.execute(query_orders, args).fetchall()              

        query_order_items = f""" SELECT                                     
                                    orders.id,                                                                              
                                    menu.name AS item_name,
                                    item_qty,
                                    item_price
                                    FROM orders
                                    JOIN order_items ON orders.id = order_id
                                    JOIN users ON users.id = user_id
                                    JOIN menu ON menu.id = item_id
                                    WHERE {user_template} = ? {extra_query}                              
                                                                            
                            """

        orders_items = db.execute(query_order_items, args).fetchall()  
        
        if date:
            query_orders_summary = f""" SELECT                                     
                                            orders.id,                                                                              
                                            menu.name AS item_name,
                                            SUM(item_qty) AS item_qty,
                                            cat
                                            FROM orders
                                            JOIN order_items ON orders.id = order_id                                            
                                            JOIN menu ON menu.id = item_id
                                            WHERE {user_template} = ? {extra_query} AND status = 1
                                            GROUP BY item_name 
                                            ORDER BY cat, item_name                              
                                                                                
                                    """

            orders_summary = db.execute(query_orders_summary, (user_id, date)).fetchall()   
        else:
            orders_summary = []

        for order in orders : 
            order['list'] = []                         
            
            for order_item in orders_items:
                if order['id'] == order_item['id']:
                    order['list'].append(order_item)           
                    
                    
        return jsonify(orders, orders_summary)
    
    finally:
        conn.commit()
        db.close()
        conn.close()          
        
        
@app.route('/update-order', methods=['POST'])
def update_order():
    user_id = session['user_id']  
    user_type = session['type'] 
    data = request.get_json()
    order_id = data[0]
    action = data[1]
    no_reg = data[2]
    csrf_token = data[3]
    session_token = session.get('_csrf_token')

    if not session_token or not csrf_token or csrf_token != session_token:
        session.clear()
        return jsonify ({"message" : "Session has been cleared"})

    today = datetime.now()
    date = today.date()    
    time = today.time() # need to add later limit time for next day order
    day = date.weekday()

    conn = sqlite3.connect('moulin.db')
    conn.row_factory = dict_factory
    db = conn.cursor()

    try:       
        
        if no_reg:
            order = db.execute("SELECT ref_order FROM orders WHERE id = ?", (order_id,)).fetchone()
            order_id = order['ref_order']          
         
        if user_type == "user": 
            order = db.execute("SELECT user_id, ref_day, type FROM orders_reg WHERE ref_order = ?", (order_id,)).fetchone() 
        else:   
            order = db.execute("""SELECT user_id, ref_day, type, owner FROM orders_reg 
                                  JOIN order_items ON order_id = ref_order
                                  JOIN menu ON menu.id  = item_id
                                  JOIN bakeries ON bakeries.id = bakery_id  
                                  WHERE ref_order = ?
                                  GROUP BY user_id                              
                               """, (order_id,)).fetchone()         
        
        extra_alert = ""        
       
        if order['user_id'] != user_id:
            if order['owner'] != user_id:
                return jsonify({"message" : "Mauvais utilisateur"})

        if action == "cancel":
            db.execute("UPDATE orders_reg SET status = 0 WHERE ref_order = ?", (order_id,))
            next_orders = db.execute("SELECT id, ref_order, date(order_date) AS date FROM orders WHERE ref_order = ? AND date(order_date) >= ?", (order_id, date)).fetchall()

            for next_order in next_orders:
                order_date = datetime.strptime(next_order['date'],"%Y-%m-%d").date()
                date_diff = order_date - date
                date_diff = date_diff.days

                if date_diff == 1:                
                    extra_alert = " sauf celle de demain (car moins de 24h en avance)" 
                    pass    
                elif date_diff == 0:                
                    extra_alert = " sauf celle d'aujourd'hui (car moins de 24h en avance)" 
                    pass                     

                elif next_order['id'] == next_order['ref_order']:
                    db.execute("UPDATE orders SET status = 0 WHERE id = ?",(next_order['id'],))

                else:
                    db.execute("DELETE FROM orders WHERE id = ?", (next_order['id'],))
                    db.execute("DELETE FROM order_items WHERE order_id = ?", (next_order['id'],))
                
                alert = "Les commandes prévues ont été annulées"
            

        elif action == "activate":

            ref_day = order['ref_day']
            type = order['type']
            days_gap = day - ref_day 
            
            if days_gap == 0:
                delta_days = 7
            elif days_gap < 0:
                delta_days = abs(days_gap)
            else:
                delta_days = 7 - days_gap       
            
            next_date = date + timedelta(days=delta_days)

            if type == "weekly":
                order_frequency = 5
                interval_days = 7
            
            check_date = next_date + timedelta(days=interval_days)
            check_date = check_date.strftime("%Y-%m-%dT00:00:00.000Z") 

            db.execute("UPDATE orders_reg SET status = 1, checkdate = ? WHERE ref_order = ?", (check_date, order_id,))

            ref_order = db.execute("SELECT user_id, total_order, ref_order, note FROM orders WHERE id = ?", (order_id,)).fetchone()  



            for i in range(order_frequency):

                order_date = next_date + timedelta(days=interval_days*i) 
                order_date = order_date.strftime("%Y-%m-%dT00:00:00.000Z")
                values_order = (ref_order['user_id'], order_date, ref_order['total_order'], ref_order['ref_order'], ref_order['note'],1)                     
                
                db.execute("""INSERT INTO orders (user_id, order_date, total_order, ref_order, note, status)
                                VALUES (?,?,?,?,?,?)
                            """, values_order)  
                conn.commit()
                
                last_id = db.execute("SELECT MAX(id) AS id FROM orders WHERE user_id = ?", (user_id,)).fetchone()              
                last_id = last_id['id']                       
                        
                last_id_items = db.execute("SELECT MAX(id) AS id FROM order_items").fetchone() 
                last_id_items = last_id_items['id']

                db.execute("""INSERT INTO order_items (order_id, item_id, item_qty, item_price, total_price)
                                SELECT order_id, item_id, item_qty, item_price, total_price FROM order_items WHERE order_id = ? 
                            """, (order_id,))                    
                
                db.execute("UPDATE order_items SET order_id = ? WHERE order_id = ? AND id > ?", (last_id, order_id, last_id_items)) 

                alert = "La commande a été activée"
                
        else:
            db.execute("UPDATE orders_reg SET status = 2 WHERE ref_order = ?", (order_id,))

            next_orders = db.execute("SELECT id FROM orders WHERE ref_order = ? AND date(order_date) > ?", (order_id, date)).fetchall()

            for next_order in next_orders:
                db.execute("DELETE FROM orders WHERE id = ?", (next_order['id'],))
                db.execute("DELETE FROM order_items WHERE order_id = ?", (next_order['id'],))
            
            alert = "La commande a été supprimée"
            
        
        return jsonify({"message" : f"{alert}{extra_alert}"})
        
       
        
    finally:
        conn.commit()
        db.close()
        conn.close()

@app.route("/cancel-order", methods=['POST'])
def cancel_order():

    user_id = session['user_id']  
    user_type = session['type']  
    data = request.get_json() 
    order_id = data[0]
    csrf_token = data[1]
    session_token = session.get('_csrf_token')

    if not session_token or not csrf_token or csrf_token != session_token:
        session.clear()
        return jsonify ({"message" : "Session has been cleared"})


    today = datetime.now()
    date = today.date()  
    time = today.time() # implement with time limit

    conn = sqlite3.connect('moulin.db')
    conn.row_factory = dict_factory
    db = conn.cursor()

    try:

        if user_type == "user":
            order = db.execute("SELECT date(order_date) AS date, user_id FROM orders WHERE id = ?", (order_id,)).fetchone()
            
        else:
            order = db.execute("""SELECT date(order_date) AS date, user_id, owner                                      
                                  FROM orders 
                                  JOIN order_items ON order_id = orders.id
                                  JOIN menu ON menu.id = item_id 
                                  JOIN bakeries ON bakeries.id = bakery_id                                
                                  WHERE orders.id = ? 
                                  GROUP BY user_id                          
                               
                               """, (order_id,)).fetchone()
        
        if order['user_id'] != user_id:  
            if order['owner'] != user_id:           
                return jsonify({"message" : "mauvais utilisateur"})      

        order_date = datetime.strptime(order['date'],"%Y-%m-%d").date()
        date_diff = order_date - date
        date_diff = date_diff.days    

        if 0 <= date_diff <= 1:
            flash('Vous ne pouvez pas annuler la commande moins de 24h avant la livraison')
            return jsonify({"message" : "Vous ne pouvez pas annuler une commande moins de 24h avant la livraison"})
        else:
            db.execute("UPDATE orders SET status = 0 WHERE id = ?", (order_id,))
            return jsonify({"message" : "Commande annulée"})
    
    finally :
        conn.commit()
        db.close()
        conn.close()


@app.route("/inscription-pro", methods=['GET','POST'])
def inscription_pro():
    step = session.get('step', 1)   

    if request.method == "GET":

        if step == 1:

            return render_template('inscription-pro1.html')
        
        elif step == 2:

            return render_template('inscription-pro2.html')
        
        elif step == 3 :

            with open('menu.csv', 'r', newline="", encoding="utf-8-sig") as menu_csv:
                menu = list(csv.DictReader(menu_csv, delimiter=";"))
            
            categories = []

            for item in menu:
                if not item['cat'] in categories:
                    categories.append(item['cat'].title())

            return render_template("inscription-pro3.html", menu=menu, categories=categories)       
        
    
    if request.method == 'POST':

        if step == 1:        
            data = request.form.to_dict()      
            print(data)                
            session['step'] = 2

            return redirect('/inscription-pro')  
        
        elif step == 2:
            data = request.form.to_dict() 
            print(data)                     
            session['step'] = 3

            return redirect('/inscription-pro') 

        if step == 3:
            data = request.form.to_dict()
            trimmed_data = {}            
            keys = list(data.keys())

            for i, key in enumerate(keys):
               if i < len(keys) - 1 and keys[i+1].startswith(key) and keys[i+1].endswith('is_checked'):
                   trimmed_data[key] = data[key]
                  
            session.pop('step') 
            return redirect('/')
            




#####################################################

def fill_orders():
    today = datetime.now().date()
    today = datetime.combine(today,datetime.min.time())
    today_str = today.strftime("%Y-%m-%dT00:00:00.000Z")
    print(today, today_str)
    
    conn = sqlite3.connect('moulin.db')
    conn.row_factory = dict_factory
    db = conn.cursor()

    try:

        orders_reg = db.execute("SELECT * FROM orders_reg").fetchall()                 

        for order in orders_reg:
            
            if order['checkdate'] == today_str and order['status']:                            
            
                order_id = order['ref_order']
                order_type = order['type']
                order_items = db.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,)).fetchall()
                order_data = db.execute("SELECT user_id, total_order, note FROM orders WHERE id = ?", (order_id,)).fetchone()               
                next_date = today + timedelta(days=28) # 28 days before next order 
                next_date = next_date.strftime("%Y-%m-%dT00:00:00.000Z")

                db.execute("INSERT INTO orders (order_date, user_id, total_order, ref_order, note, status) VALUES (?,?,?,?,?,?)", 
                            (next_date, order_data['user_id'], order_data['total_order'], order['ref_order'], order_data['note'], 1)) 

                last_id = db.execute("SELECT MAX(id) AS id FROM orders WHERE user_id = ?", (order_data['user_id'],)).fetchone()     #correct ! can conflict with multiple requests  SELECT ... WHERE user_id = order_client       
                last_id = last_id['id']

                for order_item in order_items:
                    if order_type == "weekly":                                                       
                        
                        db.execute("INSERT INTO order_items (order_id, item_id, item_qty, item_price, total_price) VALUES (?,?,?,?,?)", 
                                    (last_id, order_item['item_id'], order_item['item_qty'], order_item['item_price'], order_item['total_price'])) 
                        delta_days = 7
                        
                next_check = today + timedelta(days=delta_days)
                next_check = next_check.strftime("%Y-%m-%dT00:00:00.000Z")
                
                db.execute("UPDATE orders_reg SET checkdate = ? WHERE ref_order = ?", (next_check, order_id))
                            
    finally:
        conn.commit()
        db.close()
        conn.close()

    print("fill_orders is OK")



def load_menu():   

    def format_numeric(value):
        if isinstance(value,(float, int)):
            return str(value).replace('.', ',')
        return value 
    
    conn = sqlite3.connect('moulin.db')
    conn.row_factory = dict_factory
    db = conn.cursor()

    try:
        menu_data = db.execute("SELECT name, price, cat FROM menu GROUP BY name").fetchall()           

        with open ('menu.csv', "r", newline="", encoding="utf-8-sig") as menu_original:            
            menu_data_csv = list(csv.DictReader(menu_original, delimiter=";"))              
        
        for menu_item in menu_data:
            
            is_recorded = False
            for row in menu_data_csv:                                   
                if menu_item['name'] == row['name']:                                                       
                    is_recorded = True                    
                    break                      
            
            if not is_recorded:
                menu_data_csv.append({"name" : menu_item['name'], "price" : menu_item['price'], "cat" : menu_item['cat']})
               
             
        with open('menu.csv', 'w', newline="", encoding="utf-8-sig") as menu_updated:
            fieldnames=["name", "price", "cat"]
            menu_writer = csv.DictWriter(menu_updated, fieldnames=fieldnames, delimiter=";" )
            menu_writer.writeheader()
            menu_writer.writerows({key : format_numeric(value) for key, value in row.items()} for row in menu_data_csv)         

    finally:
        conn.commit()
        db.close()
        conn.close()



#schedule.every(20).seconds.do(fill_orders)  schedule.run_pending()  

def run_schedule(): 

    while True:
        try:             
            fill_orders()   
            load_menu()              
            
        finally:                       
            time.sleep(3600)

thread= threading.Thread(target=run_schedule)
thread.daemon = True
thread.start()


 
if __name__ == '__main__':
    app.run()
   
