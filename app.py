import json
from os import abort
import time
from flask import Flask, render_template, request, redirect, url_for, session, Response, stream_with_context, jsonify
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['SQLALCHEMY_POOL_SIZE'] = 20
app.config['SQLALCHEMY_MAX_OVERFLOW'] = 10 
app.config['SQLALCHEMY_POOL_TIMEOUT'] = 60
app.app_context().push()
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///crm.db'
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)

class User(UserMixin):
    def __init__(self, user_id, role):
        self.id = user_id
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    # Ваша логика загрузки пользователя из базы данных или другого источника
    # В зависимости от user_id, вы можете определить роль пользователя и создать объект User с учетом роли
    if user_id == 'operator':
        return User('operator', 'operator')
    elif user_id == 'manager':
        return User('manager', 'manager')
    elif user_id == "owner":
        return User('owner', 'owner')
    else:
        return None


class Request(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='Новая')
    created_at = db.Column(db.DateTime, default=datetime.now)
    birthdate = db.Column(db.Date) 

    cityzen = db.Column(db.String(100), default=" ")
    mesto_rod = db.Column(db.String(100), default=" ")
    doc = db.Column(db.String(100), default=" ")
    number_doc = db.Column(db.String(100), default=" ")
    kem_doc = db.Column(db.String(100), default=" ")
    date_of_doc = db.Column(db.String(100), default=" ")
    registration_date = db.Column(db.String(100), default=" ")
    address_reg = db.Column(db.String(100), default=" ")

    summa = db.Column(db.String(100), default=" ")
    date_of_deleviry = db.Column(db.String(100), default=" ")
    time_of_deleviry = db.Column(db.String(100), default=" ")
    address_of_deleviry = db.Column(db.String(100), default=" ")
    status_deleviry = db.Column(db.String(100), default=" ")

    operator_comments = db.relationship('Comment', backref='request', lazy=True) 
    operator_only = db.Column(db.Boolean, default=True)  
    sent_operator = db.Column(db.Boolean, default=False)  
    sent_manager = db.Column(db.Boolean, default=False)  

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    request_id = db.Column(db.Integer, db.ForeignKey('request.id'), nullable=False)


db.create_all()


@app.route('/')
@login_required
def login_main():
    print(session)
    if '_user_id' in session:
        print("in logout")
        print(session['_user_id'])
        return redirect(url_for('logout'))

    print("nothing/")
    return render_template('login.html')   


@app.route('/logout')
def logout():
    session.clear()  # Очистка сессии
    return redirect(url_for('login'))


@app.route('/operator_requests')
@login_required
def operator_requests():
    if not session.get('operator_logged_in'):
        return render_template('login.html')
    
    requests = Request.query.filter_by(operator_only=True).all()  # Получаем только заявки для операторов
    operator_comments = Comment.query.filter_by(request_id=None).all()
    manager_comments = Comment.query.filter(Comment.request_id != None).all()
    return render_template('operator_requests.html', requests=requests, operator_comments=operator_comments, manager_comments=manager_comments)


@app.route('/add_request_bot', methods=['POST'])
def add_request_bot():
    try:
        name = request.form['name']
        phone = request.form['phone']

        new_request = Request(name=name, phone=phone)

        db.session.add(new_request)
        db.session.commit()
        
        return jsonify({'message': 'Заявка успешно добавлена'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500



@app.route('/add_request', methods=['POST'])
@login_required
def add_request():
    if not session.get('operator_logged_in'):
        return render_template('login.html')     
    name = request.form['name']
    phone = request.form['phone']
    new_request = Request(name=name, phone=phone)
    db.session.add(new_request)
    db.session.commit()
    return redirect(url_for('operator_requests'))





@app.route('/processed_requests')
@login_required
def processed_requests():
    if not session.get('owner_logged_in'):
        return render_template('login.html')
    requests = Request.query.filter_by(status='Обработана менеджером').all()
    return render_template('processed_requests.html', requests=requests)


@app.route('/manager_requests')
@login_required
def manager_requests():
    if not session.get('manager_logged_in'):
        return render_template('login.html')
    requests = Request.query.filter_by(operator_only=False).filter(Request.status != 'Обработана менеджером').all()
    return render_template('manager_requests.html', requests=requests)


@app.route('/delete_request/<int:request_id>', methods=['POST'])
def delete_request(request_id):
    request_obj = Request.query.get(request_id)
    action = request.form['action']
    Comment.query.filter_by(request_id=request_id).delete()
    db.session.delete(request_obj)
    db.session.commit()

    if action == "delete_operator":
        return redirect(url_for('operator_requests'))
    elif action == "delete_manager":
        return redirect(url_for('manager_requests'))




@app.route('/manager_process_request/<int:request_id>', methods=['POST'])
def manager_process_request(request_id):
    request_obj = Request.query.get(request_id)
    action = request.form['action']
    comment_text = request.form.get('comment', '')  # Получаем текст комментария, если он был введен

    if action == 'process':
        request_obj.status = 'Обработана менеджером'
        request_obj.manager_processed = True
        db.session.commit()
    elif action == 'comment':
        if comment_text:  # Если был введен комментарий, сохраняем его
            new_comment = Comment(text=f"Менеджер: {comment_text}", request_id=request_obj.id)
            db.session.add(new_comment)
            db.session.commit()

    return redirect(url_for('manager_requests'))


@app.route('/process_request/<int:request_id>', methods=['POST'])
def process_request(request_id):
    request_obj = Request.query.get(request_id)
    comment_type = request.form['comment_type']
    comment_text = request.form.get('comment', '') 
    print(comment_text)
    if comment_type == 'comment':
        if comment_text: 
            print("if ") # Если был введен комментарий, сохраняем его
            new_comment = Comment(text=f"Оператор: {comment_text}", request_id=request_obj.id)
            db.session.add(new_comment)
            db.session.commit()        
    elif comment_type == 'transfer':
        print("transfer")
        request_obj.operator_only = False
        request_obj.status = 'Обработана оператором' 
        request_obj.sent_operator = True
        db.session.commit()
    
    return redirect(url_for('operator_requests'))


@app.route('/update_request', methods=['POST'])
@login_required 
def update_request():

    request_id = request.form['requestId']
    req = Request.query.get(request_id)

    birthdate = request.form['birthdate']
    try:
        birthdate = datetime.strptime(birthdate, '%Y-%m-%d').date() 
    except:
        birthdate = datetime.strptime("2024-01-01", '%Y-%m-%d').date() 

    mesto_rod = request.form['mesto_rod']
    cityzen = request.form['cityzen']
    number_doc = request.form['number_doc']
    doc = request.form['doc']
    kem_doc = request.form['kem_doc']
    date_of_doc = request.form['date_of_doc']
    registration_date = request.form['registration_date']
    address_reg = request.form['address_reg']
    summa = request.form['summa']
    date_of_deleviry = request.form['date_of_deleviry']
    time_of_deleviry = request.form['time_of_deleviry']
    address_of_deleviry = request.form['address_of_deleviry']
    status_deleviry = request.form['status_deleviry']

    req.birthdate = birthdate
    req.mesto_rod = mesto_rod
    req.cityzen = cityzen
    req.number_doc = number_doc
    req.doc = doc
    req.kem_doc = kem_doc
    req.mesto_rod = kem_doc
    req.date_of_doc = date_of_doc
    req.registration_date = registration_date
    req.address_reg = address_reg
    req.summa = summa
    req.date_of_deleviry = date_of_deleviry
    req.time_of_deleviry = time_of_deleviry
    req.address_of_deleviry = address_of_deleviry
    req.status_deleviry = status_deleviry

    db.session.commit()
    return redirect(url_for(f'{current_user.role}_requests'))


@app.route('/update_birthdate', methods=['POST'])
@login_required 
def update_birthdate():
    birthdate = request.form['birthdate']
    request_id = request.form['requestId']  # Переименовали переменную для избежания конфликта
    req = Request.query.get(request_id)
    print(birthdate)
    try:
        birthdate = datetime.strptime(birthdate, '%Y-%m-%d').date() 
    except:
        return redirect(url_for(f'{current_user.role}_requests'))
    req.birthdate = birthdate
    db.session.commit()
    return redirect(url_for(f'{current_user.role}_requests'))



@app.route('/update_mesto_rod', methods=['POST'])
@login_required 
def update_mesto_rod():
    mesto_rod = request.form['mesto_rod']
    request_id = request.form['requestId']  # Переименовали переменную для избежания конфликта
    req = Request.query.get(request_id) 
    req.mesto_rod = mesto_rod
    db.session.commit()
    return redirect(url_for(f'{current_user.role}_requests'))

@app.route('/update_cityzen', methods=['POST'])
@login_required 
def update_cityzen():
    cityzen = request.form['cityzen']
    request_id = request.form['requestId']  # Переименовали переменную для избежания конфликта
    req = Request.query.get(request_id) 
    req.cityzen = cityzen
    db.session.commit()
    print(current_user.role)
    return redirect(url_for(f'{current_user.role}_requests'))
    # if current_user.role == 'operator':
    #     return redirect(url_for('operator_requests'))
    # elif current_user.role == 'manager':
    #     return redirect(url_for('manager_requests'))

@app.route('/update_number_doc', methods=['POST'])
@login_required 
def update_number_doc():
    number_doc = request.form['number_doc']
    request_id = request.form['requestId'] 
    req = Request.query.get(request_id)
    req.number_doc = number_doc
    db.session.commit()
    return redirect(url_for(f'{current_user.role}_requests'))

@app.route('/update_doc', methods=['POST'])
@login_required 
def update_doc():
    doc = request.form['doc']
    request_id = request.form['requestId'] 
    req = Request.query.get(request_id)
    req.doc = doc
    db.session.commit()
    return redirect(url_for(f'{current_user.role}_requests'))


@app.route('/update_kem_doc', methods=['POST'])
@login_required 
def update_kem_doc():
    kem_doc = request.form['kem_doc']
    request_id = request.form['requestId'] 
    req = Request.query.get(request_id)
    req.kem_doc = kem_doc
    db.session.commit()
    return redirect(url_for(f'{current_user.role}_requests'))

@app.route('/update_date_of_doc', methods=['POST'])
@login_required 
def update_date_of_doc():
    date_of_doc = request.form['date_of_doc']
    request_id = request.form['requestId'] 
    req = Request.query.get(request_id)
    req.date_of_doc = date_of_doc
    db.session.commit()
    return redirect(url_for(f'{current_user.role}_requests'))


@app.route('/update_registration_date', methods=['POST'])
@login_required 
def update_registration_date():
    registration_date = request.form['registration_date']
    request_id = request.form['requestId'] 
    req = Request.query.get(request_id)
    req.registration_date = registration_date
    db.session.commit()
    return redirect(url_for(f'{current_user.role}_requests'))


@app.route('/update_address_reg', methods=['POST'])
@login_required 
def update_address_reg():
    address_reg = request.form['address_reg']
    request_id = request.form['requestId'] 
    req = Request.query.get(request_id)
    req.address_reg = address_reg
    db.session.commit()
    return redirect(url_for(f'{current_user.role}_requests'))

@app.route('/update_summa', methods=['POST'])
@login_required 
def update_summa():
    summa = request.form['summa']
    request_id = request.form['requestId'] 
    req = Request.query.get(request_id)
    req.summa = summa
    db.session.commit()
    return redirect(url_for(f'{current_user.role}_requests'))

@app.route('/update_date_of_deleviry', methods=['POST'])
@login_required 
def update_date_of_deleviry():
    date_of_deleviry = request.form['date_of_deleviry']
    request_id = request.form['requestId'] 
    req = Request.query.get(request_id)
    req.date_of_deleviry = date_of_deleviry
    db.session.commit()
    return redirect(url_for(f'{current_user.role}_requests'))

@app.route('/update_time_of_deleviry', methods=['POST'])
@login_required 
def update_time_of_deleviry():
    time_of_deleviry = request.form['time_of_deleviry']
    request_id = request.form['requestId'] 
    req = Request.query.get(request_id)
    req.time_of_deleviry = time_of_deleviry
    db.session.commit()
    return redirect(url_for(f'{current_user.role}_requests'))

@app.route('/update_address_of_deleviry', methods=['POST'])
@login_required 
def update_address_of_deleviry():
    address_of_deleviry = request.form['address_of_deleviry']
    request_id = request.form['requestId'] 
    req = Request.query.get(request_id)
    req.address_of_deleviry = address_of_deleviry
    db.session.commit()
    return redirect(url_for(f'{current_user.role}_requests'))

@app.route('/update_status_deleviry', methods=['POST'])
def update_status_deleviry():
    status_deleviry = request.form['status_deleviry']
    request_id = request.form['requestId'] 
    req = Request.query.get(request_id)
    req.status_deleviry = status_deleviry
    db.session.commit()
    return redirect(url_for(f'{current_user.role}_requests'))

@login_manager.unauthorized_handler
def unauthorized():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Ваша логика проверки имени пользователя и пароля
        username = request.form['username']
        password = request.form['password']
        
        if username == 'operator' and password == 'operator_password':
            session.clear()
            session['operator_logged_in'] = True
            user = User("operator", "operator")
            login_user(user)
            return redirect(url_for('operator_requests'))
        elif username == 'manager' and password == 'manager_password':
            session.clear()
            session['manager_logged_in'] = True
            user = User('manager', 'manager')
            login_user(user)
            return redirect(url_for('manager_requests'))
        elif username == 'owner' and password == 'owner':
            session.clear()
            session['owner_logged_in'] = True
            user = User('owner', 'owner')   
            login_user(user)
            return redirect(url_for('processed_requests'))        
        else:
            return ('Неверное имя пользователя или пароль', 'error')
    
    return render_template('login.html')


@app.route('/stream')
@login_required
def stream():
    def generate():
        while True:
            # Ваша логика для получения новых заявок
            new_request = get_new_request()  # Функция, которая возвращает новые заявки
            if new_request:
                yield f"data: {new_request}\n\n"  # Отправить новую заявку клиенту
            time.sleep(1)  # Пауза для имитации получения новых заявок
        
    return Response(stream_with_context(generate()), content_type='text/event-stream')


def get_new_request():
    new_requests = Request.query.filter_by(sent_operator=True, sent_manager=False).all()
    
    # Преобразуем список заявок в список словарей
    new_requests_data = [{"id": request.id, "name": request.name, "phone": request.phone, "status": request.status, "operator_comments": [comment.text for comment in request.operator_comments], "birthdate": request.birthdate, "cityzen": request.cityzen} for request in new_requests]
    if new_requests_data != []:
        print(new_requests_data)
        for data in new_requests:
            request_obj = Request.query.get(data.id)
            request_obj.sent_operator = False
            db.session.commit()
        
        return json.dumps(new_requests_data)

if __name__ == '__main__':
    app.run(debug=True)

