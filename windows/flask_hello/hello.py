#coding=utf-8

from flask import Flask, redirect, request, jsonify,render_template,url_for
from threading import Thread
from flask_mail import Mail,Message
import json
app=Flask(__name__)
app.config["DEBUG"]=True

app.config['MAIL_DEBUG'] = True             # 开启debug，便于调试看信息
app.config['MAIL_SUPPRESS_SEND'] = False    # 发送邮件，为True则不发送
app.config["MAIL_SERVER"] = "smtp.qq.com"
app.config["MAIL_PORT"] = 465
app.config["MAIL_USE_SSL"] = True
app.config["MAIL_USE_TLS"] = False
app.config["MAIL_USERNAME"] = "92468880@qq.com"
app.config["MAIL_DEFAULT_SENDER"] = "92468880@qq.com"
app.config["MAIL_PASSWORD"] = "zqmzwxamhtiqbdgg"
mail = Mail(app)

@app.route("/send_mail")
def send_mail():
    """
    发送邮件
    """
    message = Message("标题",recipients=["chen.wenjun@vhd.com.cn"])
    message.body = "内容"
    
    t = Thread(target=send_email,args=(message,))
    t.start()
    
    return "发送成功"
    
def send_email(msg):
    with app.app_context():
        mail.send(msg)


@app.route("/")
def index():
    #传递参数给html,html中获取方式： {{变量}}
    test=1
    return render_template("demo.html",num=test)


@app.route("/login",methods=["GET","POST"])
def login_fun():
    print(request.method)
    if request.method == "GET":
        return "please enter uaername..."
    else:
        #postman 中发送方式为URL params，而不是Headers
        username = request.args.get('username') or "no username"
        pwd = request.args.get('pwd') or "no pwd"
        print('args参数是', username,pwd)
        return username+ " " + pwd + " is ok"


@app.route("/json",methods=["POST"])
def json_fun():
    #postman 中发送方式Headers,raw,json
    myjson=json.loads(request.data)
    print("username:",myjson['username'])
    print("pwd:", str(myjson["pwd"]))
    return jsonify(msg="ok")


@app.route("/string/<string:username>")
def string_fun(username):
    return username +" "+ username


@app.route("/int/<int:post_id>")
def int_fun(post_id):
    return str(post_id)


@app.route("/baidu")
def baidu_fun():
    #return redirect("http://www.baidu.com")
    return redirect(url_for("string_fun",username="baidu"))


if __name__ == "__main__":
    app.run(host="0.0.0.0")
