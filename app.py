from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "uma-chave-secreta-bem-grande"  # troque em produção

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "termos.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class Termo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome_colab = db.Column(db.String(255))
    data_doc = db.Column(db.String(10))
    local = db.Column(db.String(255))
    data_assinatura = db.Column(db.String(10))
    data_entrega = db.Column(db.String(10))
    data_devolucao = db.Column(db.String(10))
    equipamentos_json = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)


class TipoEquipamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(255), unique=True, nullable=False)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)


with app.app_context():
    db.create_all()
    # cria usuário admin padrão se não existir
    if not User.query.filter_by(username="admin").first():
        admin_user = User(
            username="admin",
            password_hash=generate_password_hash("admin"),
            is_admin=True,
        )
        db.session.add(admin_user)
        db.session.commit()


def is_logged_in():
    return session.get("user_id") is not None


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    return User.query.get(uid)


def is_admin():
    user = current_user()
    return bool(user and user.is_admin)


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        pwd = request.form.get("password", "").strip()
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, pwd):
            session["user_id"] = user.id
            session["username"] = user.username
            session["is_admin"] = user.is_admin
            return redirect(url_for("termo"))
        flash("Usuário ou senha inválidos.", "erro")
    if is_logged_in():
        return redirect(url_for("termo"))
    return render_template("login.html")


@app.route("/sair")
def sair():
    session.clear()
    return redirect(url_for("login"))


@app.route("/usuarios", methods=["GET", "POST"])
def usuarios():
    if not is_admin():
        return redirect(url_for("termo"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        is_admin_flag = bool(request.form.get("is_admin"))

        if not username or not password:
            flash("Usuário e senha são obrigatórios.", "erro")
        elif User.query.filter_by(username=username).first():
            flash("Nome de usuário já existe.", "erro")
        else:
            u = User(
                username=username,
                password_hash=generate_password_hash(password),
                is_admin=is_admin_flag,
            )
            db.session.add(u)
            db.session.commit()
            flash("Usuário criado com sucesso.", "sucesso")
        return redirect(url_for("usuarios"))

    usuarios = User.query.order_by(User.username.asc()).all()
    return render_template("usuarios.html", usuarios=usuarios)


@app.route("/usuarios/<int:user_id>/excluir", methods=["POST"])
def excluir_usuario(user_id):
    if not is_admin():
        return redirect(url_for("termo"))
    user = User.query.get_or_404(user_id)
    if user.username == "admin":
        flash("Não é permitido excluir o usuário admin padrão.", "erro")
        return redirect(url_for("usuarios"))
    db.session.delete(user)
    db.session.commit()
    flash("Usuário excluído.", "sucesso")
    return redirect(url_for("usuarios"))


@app.route("/usuarios/<int:user_id>/editar", methods=["GET", "POST"])
def editar_usuario(user_id):
    if not is_admin():
        return redirect(url_for("termo"))
    usuario = User.query.get_or_404(user_id)

    if request.method == "POST":
        novo_username = request.form.get("username", "").strip()
        nova_senha = request.form.get("password", "").strip()
        is_admin_flag = bool(request.form.get("is_admin"))

        if not novo_username:
            flash("Usuário é obrigatório.", "erro")
            return redirect(url_for("editar_usuario", user_id=user_id))

        existente = User.query.filter(
            User.username == novo_username, User.id != usuario.id
        ).first()
        if existente:
            flash("Já existe outro usuário com esse nome.", "erro")
            return redirect(url_for("editar_usuario", user_id=user_id))

        usuario.username = novo_username

        if nova_senha:
            usuario.password_hash = generate_password_hash(nova_senha)

        if usuario.username == "admin":
            usuario.is_admin = True
        else:
            usuario.is_admin = is_admin_flag

        db.session.commit()
        flash("Usuário atualizado com sucesso.", "sucesso")
        return redirect(url_for("usuarios"))

    return render_template("usuario_editar.html", usuario=usuario)


@app.route("/termos")
def listar_termos():
    if not is_logged_in():
        return redirect(url_for("login"))
    termos = Termo.query.order_by(Termo.criado_em.desc()).all()
    return render_template("termos.html", termos=termos)


@app.route("/termo", methods=["GET", "POST"])
def termo():
    if not is_logged_in():
        return redirect(url_for("login"))

    if request.method == "POST":
        nome_colab = request.form.get("nomeColab")
        data_doc = request.form.get("dataDoc")
        local = request.form.get("local")
        data_assinatura = request.form.get("dataAssinatura")
        data_entrega = request.form.get("dataEntrega")
        data_devolucao = request.form.get("dataDevolucao")

        tipos = request.form.getlist("tipo[]")
        patrim = request.form.getlist("patrimonio[]")
        obs = request.form.getlist("obs[]")

        import json
        equipamentos = []
        tamanho = max(len(tipos), len(patrim), len(obs))
        for i in range(tamanho):
            tipo_val = tipos[i] if i < len(tipos) else ""
            patrimonio_val = patrim[i] if i < len(patrim) else ""
            obs_val = obs[i] if i < len(obs) else ""

            if not (tipo_val or patrimonio_val or obs_val):
                continue

            equipamentos.append(
                {
                    "tipo": tipo_val,
                    "patrimonio": patrimonio_val,
                    "obs": obs_val,
                }
            )

        # garantir que novos tipos sejam salvos na tabela de tipos
        tipos_unicos = {e["tipo"].strip() for e in equipamentos if e["tipo"].strip()}
        if tipos_unicos:
            tipos_existentes = {
                t.nome.lower(): t for t in TipoEquipamento.query.filter(
                    TipoEquipamento.nome.in_(tipos_unicos)
                ).all()
            }
            for nome in tipos_unicos:
                if nome.lower() not in tipos_existentes:
                    db.session.add(TipoEquipamento(nome=nome))
        equipamentos_json = json.dumps(equipamentos, ensure_ascii=False)

        termo = Termo(
            nome_colab=nome_colab,
            data_doc=data_doc,
            local=local,
            data_assinatura=data_assinatura,
            data_entrega=data_entrega,
            data_devolucao=data_devolucao,
            equipamentos_json=equipamentos_json
        )
        db.session.add(termo)
        db.session.commit()
        flash("Termo salvo com sucesso!", "sucesso")
        return redirect(url_for("termo"))

    # GET: carregar tipos cadastrados para o combo
    tipos_cadastrados = (
        TipoEquipamento.query.order_by(TipoEquipamento.nome.asc()).all()
    )
    return render_template("termo.html", tipos_cadastrados=tipos_cadastrados)


if __name__ == "__main__":
    app.run(debug=True)

