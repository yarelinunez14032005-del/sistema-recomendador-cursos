from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
import re
import os
from werkzeug.utils import secure_filename
from flask import session
import uuid


app = Flask(__name__)
app.secret_key = "mi_clave_secreta"

from functools import wraps
from flask import redirect, session

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'rol' not in session or session['rol'] != 'admin':
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

UPLOAD_FOLDER = 'static/materiales'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# =========================
# BASE DE DATOS
# =========================
def crear_bd():
    conexion = sqlite3.connect("cursos.db")
    cursor = conexion.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cursos(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT,
        categoria TEXT,
        nivel TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS materiales(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        curso_id INTEGER,
        archivo TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT,
        correo TEXT UNIQUE,
        password TEXT,
        rol TEXT
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS progreso(
     id INTEGER PRIMARY KEY AUTOINCREMENT,
     user_id INTEGER,
     curso_id INTEGER,
     material_id INTEGER
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS configuracion(
     user_id INTEGER PRIMARY KEY,
     tema TEXT,
     color TEXT,
     categoria_favorita TEXT,
     nivel_preferido TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS historial_cursos (
     id INTEGER PRIMARY KEY AUTOINCREMENT,
     user_id INTEGER,
     curso_id INTEGER,
     fecha TEXT
    )
    """)


    cursor.execute("""
    CREATE TABLE IF NOT EXISTS materiales_vistos (
     id INTEGER PRIMARY KEY AUTOINCREMENT,
     user_id INTEGER,
     material_id INTEGER
    )
    """)

    cursor.execute("""
     CREATE TABLE IF NOT EXISTS cursos_completados (
     id INTEGER PRIMARY KEY AUTOINCREMENT,
     user_id INTEGER,
     curso_id INTEGER,
     fecha TEXT
    )
    """)

    conexion.commit()
    conexion.close()


crear_bd()


# =========================
# LOGIN
# =========================
@app.route('/login')
def login():
    return render_template('login.html')


@app.route('/validar', methods=['POST'])
def validar():
    correo = request.form['correo']
    password = request.form['password']

    conn = sqlite3.connect("cursos.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, nombre, correo, rol 
        FROM usuarios
        WHERE correo=? AND password=?
    """, (correo, password))

    usuario = cursor.fetchone()
    conn.close()

    if usuario:
        session['user_id'] = usuario[0]
        session['usuario'] = usuario[1]
        session['rol'] = usuario[3]

        return redirect('/')

    return "Credenciales incorrectas"


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# =========================
# HOME
# =========================
@app.route('/')
def inicio():

    if 'user_id' not in session:
        return redirect('/login')
    
    if session.get('rol') == 'admin':
       return redirect('/admin')

    conn = sqlite3.connect("cursos.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM usuarios")
    total_usuarios = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM cursos")
    total_cursos = cursor.fetchone()[0]

    # LEER CONFIGURACIÓN DEL USUARIO
    cursor.execute("""
    SELECT tema, color
    FROM configuracion
    WHERE user_id=?
    """, (session['user_id'],))

    config = cursor.fetchone()

    print("CONFIG EN INICIO:", config)


    cursor.execute("""
    SELECT COUNT(DISTINCT curso_id)
     FROM historial_cursos
     WHERE user_id=?
    """, (session['user_id'],))

    cursos_vistos = cursor.fetchone()[0]

    if cursos_vistos >= 5:
     progreso = 100
    elif cursos_vistos >= 4:
     progreso = 80
    elif cursos_vistos >= 3:
     progreso = 60
    elif cursos_vistos >= 2:
     progreso = 40
    elif cursos_vistos >= 1:
     progreso = 20
    else:
        progreso = 0

    conn.close()

    return render_template(
        'index.html',
        usuario=session['usuario'],
        progreso=progreso,
        total_usuarios=total_usuarios,
        total_cursos=total_cursos,
        config=config
    )

#registro 
@app.route('/registro', methods=['GET', 'POST'])
def registro():

    mensaje = None

    if request.method == 'POST':

        nombre = request.form['nombre']
        correo = request.form['correo']
        password = request.form['password']

        conn = sqlite3.connect("cursos.db")
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO usuarios(nombre, correo, password, rol)
                VALUES(?,?,?,?)
            """, (nombre, correo, password, 'usuario'))

            conn.commit()
            conn.close()

            return redirect('/login')

        except sqlite3.IntegrityError:
            mensaje = "El correo ya está registrado"

    return render_template('registro.html', mensaje=mensaje)

# =========================
# RECOMENDAR
# =========================
@app.route('/recomendar', methods=['GET', 'POST'])
def recomendar():

    if request.method == 'POST':
        categoria = request.form.get('categoria')
        session['categoria'] = categoria  # guardamos

    else:
        categoria = session.get('categoria')

    if not categoria:
        return redirect('/')

    conexion = sqlite3.connect("cursos.db")
    cursor = conexion.cursor()

    cursor.execute(
        "SELECT id, nombre, nivel FROM cursos WHERE categoria=?",
        (categoria,)
    )

    cursos = cursor.fetchall()
    conexion.close()

    return render_template(
        'resultados.html',
        cursos=cursos,
        categoria=categoria
    )


# =========================
# LISTA DE CURSOS (USUARIO)
# =========================
@app.route('/cursos')
def cursos():

    conn = sqlite3.connect("cursos.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM cursos")
    cursos = cursor.fetchall()

    conn.close()

    return render_template("cursos_usuario.html", cursos=cursos)


# =========================
# VER CURSO (ÚNICA RUTA CORRECTA)
# =========================
@app.route('/curso/<int:id>')
def ver_curso(id):
    if 'user_id' not in session:
        return redirect('/login')
    back = request.args.get('back', '/cursos')

    conn = sqlite3.connect("cursos.db")
    cursor = conn.cursor()

    # Verificar si ya visitó el curso
    cursor.execute("""
    SELECT *
    FROM historial_cursos
    WHERE user_id=?
    AND curso_id=?
    """,
    (
    session['user_id'],
    id
    ))

    existe = cursor.fetchone()

    if not existe:
    
    # Registrar visita
     cursor.execute("""
     INSERT INTO historial_cursos
     (user_id, curso_id, fecha)
     VALUES (?, ?, datetime('now'))
     """,
    (
        session['user_id'],
        id
    ))

    conn.commit()

    #CURSO
    cursor.execute("SELECT * FROM cursos WHERE id=?", (id,))
    curso = cursor.fetchone()
    #MA
    cursor.execute("SELECT * FROM materiales WHERE curso_id=?", (id,))
    materiales = cursor.fetchall()

    # Total materiales del curso
    cursor.execute("""
    SELECT COUNT(*)
    FROM materiales
    WHERE curso_id=?
    """, (id,))

    total_materiales = cursor.fetchone()[0]

    # Materiales vistos
    cursor.execute("""
    SELECT COUNT(DISTINCT mv.material_id)
    FROM materiales_vistos mv
    INNER JOIN materiales m
    ON mv.material_id = m.id
    WHERE mv.user_id=?
    AND m.curso_id=?
    """,
    (
     session['user_id'],
     id
    ))

    vistos = cursor.fetchone()[0]
     
    progreso = vistos * 20

    if progreso > 100:
     progreso = 100



     if progreso == 100:

      cursor.execute("""
       SELECT *
       FROM cursos_completados
       WHERE user_id=?
       AND curso_id=?
       """,
       (
        session['user_id'],
        id
    ))

    existe_completado = cursor.fetchone()

    if not existe_completado:

        cursor.execute("""
        INSERT INTO cursos_completados
        (user_id, curso_id, fecha)
        VALUES (?, ?, datetime('now'))
        """,
        (
            session['user_id'],
            id
        ))

        conn.commit()

        print("CURSO COMPLETADO:", id)

        print("TOTAL MATERIALES:", total_materiales)
        print("MATERIALES VISTOS:", vistos)
        print("PROGRESO:", progreso)
    

    conn.close()

    return render_template(
        "curso.html",
        curso=curso,
        materiales=materiales,
        back=back,
        progreso=progreso
    )


# =========================
# SUBIR MATERIAL
# =========================
@app.route('/subir_material')
@admin_required
def subir_material():

    mensaje = request.args.get('msg')

    conn = sqlite3.connect("cursos.db")
    cursor = conn.cursor()

    cursor.execute("SELECT id, nombre FROM cursos")
    cursos = cursor.fetchall()

    conn.close()

    return render_template(
        "subir_material.html",
        cursos=cursos,
        mensaje=mensaje
    )

#GUARDAR MATERIAL 
@app.route('/guardar_material', methods=['POST'])
@admin_required
def guardar_material():

    archivo = request.files['archivo']
    curso_id = request.form['curso_id']

    nombre_original = secure_filename(archivo.filename)
    nombre_archivo = str(uuid.uuid4()) + "_" + nombre_original

    ruta = os.path.join(os.getcwd(), "static", "materiales", nombre_archivo)

    archivo.save(ruta)
    print("ARCHIVO GUARDADO:", nombre_archivo)

    conn = sqlite3.connect("cursos.db")
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO materiales(curso_id, archivo) VALUES(?,?)",
        (curso_id, nombre_archivo)
    )

    conn.commit()
    conn.close()

    return redirect('/subir_material?msg=archivo_subido')

#GUARDAR CURSO 
@app.route('/agregar_curso', methods=['POST'])
@admin_required
def guardar_curso():

    nombre = request.form['nombre']
    categoria = request.form['categoria']
    nivel = request.form['nivel']

    conn = sqlite3.connect("cursos.db")
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO cursos(nombre, categoria, nivel)
        VALUES(?,?,?)
    """, (nombre, categoria, nivel))

    conn.commit()
    conn.close()

    return redirect('/admin/cursos')

# =========================
# ELIMINAR MATERIAL
# =======================
@app.route('/eliminar_material/<int:id>')
@admin_required
def eliminar_material(id):

    conn = sqlite3.connect("cursos.db")
    cursor = conn.cursor()

    cursor.execute("SELECT archivo FROM materiales WHERE id=?", (id,))
    archivo = cursor.fetchone()

    if archivo:
        ruta = os.path.join("static/materiales", archivo[0])
        if os.path.exists(ruta):
            os.remove(ruta)

    cursor.execute("DELETE FROM materiales WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect(request.referrer)


# =========================
# ELIMINAR CURSO (CORREGIDO)
# =========================
@app.route('/eliminar_curso/<int:id>')
@admin_required
def eliminar_curso(id):

    conn = sqlite3.connect("cursos.db")
    cursor = conn.cursor()

    cursor.execute("DELETE FROM cursos WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect('/admin/cursos')


# =========================
# ADMIN CURSOS
# =========================
@app.route('/admin/agregar_curso', methods=['GET', 'POST'])
@admin_required
def agregar_curso():

    mensaje = None

    if request.method == 'POST':

        nombre = request.form['nombre']
        categoria = request.form['categoria']
        nivel = request.form['nivel']

        conn = sqlite3.connect("cursos.db")
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO cursos(nombre, categoria, nivel)
            VALUES(?,?,?)
        """, (nombre, categoria, nivel))

        conn.commit()
        conn.close()

        mensaje = "✅ Curso guardado correctamente"

    return render_template("agregar_curso.html", mensaje=mensaje)


# =========================
# EDITAR CURSO
# =========================
@app.route('/editar_curso/<int:id>', methods=['GET', 'POST'])
@admin_required
def editar_curso(id):

    conn = sqlite3.connect("cursos.db")
    cursor = conn.cursor()

    if request.method == 'POST':

        nombre = request.form['nombre']
        categoria = request.form['categoria']
        nivel = request.form['nivel']

        cursor.execute("""
            UPDATE cursos
            SET nombre=?, categoria=?, nivel=?
            WHERE id=?
        """, (nombre, categoria, nivel, id))

        conn.commit()

    # 👇 CURSO
    cursor.execute("SELECT * FROM cursos WHERE id=?", (id,))
    curso = cursor.fetchone()

    # 👇 MATERIALES (ESTO FALTABA)
    cursor.execute("SELECT * FROM materiales WHERE curso_id=?", (id,))
    materiales = cursor.fetchall()

    conn.close()

    return render_template(
        "editar_curso.html",
        curso=curso,
        materiales=materiales
    )

# =========================
# PERFIL DE USUARIO
# =========================
@app.route('/perfil')
def perfil():
    if 'user_id' not in session:
        return redirect('/login')

    conn = sqlite3.connect("cursos.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT nombre, correo, rol
        FROM usuarios
        WHERE id=?
    """, (session['user_id'],))

    user = cursor.fetchone()
    conn.close()

    usuario = {
        "nombre": user[0],
        "email": user[1],
        "rol": user[2]
    }

    return render_template("perfil.html", usuario=usuario)

# =========================
# EDITAR PERFIL 
# =========================
@app.route('/editar_perfil', methods=['GET', 'POST'])
def editar_perfil():

    if 'user_id' not in session:
        return redirect('/login')

    conn = sqlite3.connect("cursos.db")
    cursor = conn.cursor()

    # GUARDAR CAMBIOS
    if request.method == 'POST':

        nombre = request.form['nombre']
        correo = request.form['correo']

        cursor.execute("""
            UPDATE usuarios
            SET nombre=?, correo=?
            WHERE id=?
        """, (nombre, correo, session['user_id']))

        conn.commit()
        conn.close()

        return redirect('/perfil')

    # MOSTRAR DATOS ACTUALES
    cursor.execute("""
        SELECT nombre, correo, rol
        FROM usuarios
        WHERE id=?
    """, (session['user_id'],))

    user = cursor.fetchone()
    conn.close()

    usuario = {
        "nombre": user[0],
        "email": user[1],
        "rol": user[2]
    }

    return render_template("editar_perfil.html", usuario=usuario)

 #cambiar contraseña 
@app.route('/cambiar_password', methods=['GET', 'POST'])
def cambiar_password():

    if 'user_id' not in session:
        return redirect('/login')

    if request.method == 'POST':

        nueva = request.form['password']

        conn = sqlite3.connect("cursos.db")
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE usuarios
            SET password=?
            WHERE id=?
        """, (nueva, session['user_id']))

        conn.commit()
        conn.close()

        return redirect('/perfil')

    return render_template('cambiar_password.html')

#configuracion 
@app.route('/configuracion', methods=['GET', 'POST'])
def configuracion():

    if 'user_id' not in session:
        return redirect('/login')

    conn = sqlite3.connect("cursos.db")
    cursor = conn.cursor()

    user_id = session['user_id']

    if request.method == 'POST':

        tema = request.form.get('tema')
        color = request.form.get('color')
        categoria = request.form.get('categoria')
        nivel = request.form.get('nivel')

        print("POST RECIBIDO")
        print("Tema:", tema)
        print("Color:", color)
        print("Categoria:", categoria)
        print("Nivel:", nivel)

        cursor.execute("""
        INSERT OR REPLACE INTO configuracion
        (
            user_id,
            tema,
            color,
            categoria_favorita,
            nivel_preferido
        )
        VALUES(?,?,?,?,?)
        """,
        (
            user_id,
            tema,
            color,
            categoria,
            nivel
        ))

        conn.commit()

    cursor.execute("""
    SELECT *
    FROM configuracion
    WHERE user_id=?
    """, (user_id,))
    

    config = cursor.fetchone()

    print("CONFIG COMPLETA:", config)

    conn.close()

    return render_template(
        'configuracion.html',
        config=config
    )
#Administracion
@app.route('/admin')
def admin():

    if not session.get('user_id'):
       return redirect('/login')

    if session.get('rol') != 'admin':
        return redirect('/')

    return render_template('admin.html', usuario=session.get('usuario'))

#administracion de usuario
@app.route('/admin/usuarios')
@admin_required
def usuarios():

    conn = sqlite3.connect("cursos.db")
    cursor = conn.cursor()

    cursor.execute("SELECT id, nombre, correo, rol FROM usuarios")
    usuarios = cursor.fetchall()

    conn.close()

    return render_template("usuarios.html", usuarios=usuarios)

#ADMIN CURSO 
@app.route('/admin/curso/<int:id>')
@admin_required
def ver_curso_admin(id):

    conn = sqlite3.connect("cursos.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM cursos WHERE id=?", (id,))
    curso = cursor.fetchone()

    cursor.execute("SELECT * FROM materiales WHERE curso_id=?", (id,))
    materiales = cursor.fetchall()

    conn.close()

    return render_template(
        "admin_ver_curso.html",
        curso=curso,
        materiales=materiales
    )
# admin curso 
@app.route('/admin/cursos')
@admin_required
def admin_cursos():

    conn = sqlite3.connect("cursos.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM cursos")
    cursos = cursor.fetchall()

    conn.close()

    return render_template("admin_cursos.html", cursos=cursos)

#ver usuarios 
@app.route('/usuarios')
@admin_required
def ver_usuarios():

    conn = sqlite3.connect("cursos.db")
    cursor = conn.cursor()

    cursor.execute("SELECT id, nombre, correo, rol FROM usuarios")
    usuarios = cursor.fetchall()

    conn.close()

    return render_template("usuarios.html", usuarios=usuarios)

#editar material 
@app.route('/editar_material/<int:id>', methods=['GET', 'POST'])
@admin_required
def editar_material(id):

    conn = sqlite3.connect("cursos.db")
    cursor = conn.cursor()

    if request.method == 'POST':

        archivo = request.files['archivo']

        if archivo:

            nombre = secure_filename(archivo.filename)
            ruta = os.path.join(app.config['UPLOAD_FOLDER'], nombre)
            archivo.save(ruta)

            cursor.execute("""
                UPDATE materiales
                SET archivo=?
                WHERE id=?
            """, (nombre, id))

            conn.commit()

        conn.close()
        return redirect(request.referrer)

    cursor.execute("SELECT * FROM materiales WHERE id=?", (id,))
    material = cursor.fetchone()

    conn.close()

    return render_template("editar_material.html", material=material)

#recuperar contraseña 
@app.route('/recuperar_password', methods=['GET', 'POST'])
def recuperar_password():

    mensaje = None

    if request.method == 'POST':

        correo = request.form['correo']

        conn = sqlite3.connect("cursos.db")
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM usuarios WHERE correo=?", (correo,))
        user = cursor.fetchone()

        if user:
            mensaje = "Usuario encontrado. Contacta al administrador para restablecer contraseña."
        else:
            mensaje = "Correo no registrado."

        conn.close()
 
    return render_template("recuperar_password.html", mensaje=mensaje)

#cursos de categoria
@app.route('/cursos/categoria/<nombre>')
def cursos_por_categoria(nombre):

    conn = sqlite3.connect("cursos.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, nombre, nivel
        FROM cursos
        WHERE LOWER(categoria)=?
    """, (nombre.lower(),))

    cursos = cursor.fetchall()
    conn.close()

    return render_template(
        "resultados.html",
        cursos=cursos,
        categoria=nombre
    )

#progreso 
@app.route('/progreso')
def progreso():

    if 'user_id' not in session:
        return redirect('/login')

    conn = sqlite3.connect("cursos.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM cursos")
    total_cursos = cursor.fetchone()[0]

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS progreso(
     id INTEGER PRIMARY KEY AUTOINCREMENT,
     user_id INTEGER,
     curso_id INTEGER,
     completado INTEGER DEFAULT 0
    )
    """)
    completados = cursor.fetchone()[0]

    conn.close()

    porcentaje = 0

    if total_cursos > 0:
        porcentaje = round((completados / total_cursos) * 100)

    return render_template(
        "progreso.html",
        porcentaje=porcentaje,
        completados=completados,
        total=total_cursos
    )

#completar 
@app.route('/completar/<int:curso_id>')
def completar(curso_id):

    if 'user_id' not in session:
        return redirect('/login')

    conn = sqlite3.connect("cursos.db")
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO progreso(user_id, curso_id, completado)
        VALUES (?, ?, 1)
    """, (session['user_id'], curso_id))

    conn.commit()
    conn.close()

    return redirect('/cursos')

#abrir material
@app.route('/abrir_material/<int:id>')
def abrir_material(id):

    if 'user_id' not in session:
        return redirect('/login')

    conn = sqlite3.connect("cursos.db")
    cursor = conn.cursor()

    # Verificar si ya abrió este material
    cursor.execute("""
    SELECT *
    FROM materiales_vistos
    WHERE user_id=?
    AND material_id=?
    """,
    (
        session['user_id'],
        id
    ))

    existe = cursor.fetchone()

    print("MATERIAL ABIERTO:", id)

    if not existe:

        cursor.execute("""
        INSERT INTO materiales_vistos
        (user_id, material_id)
        VALUES (?, ?)
        """,
        (
            session['user_id'],
            id
        ))

        conn.commit()

        print("GUARDANDO MATERIAL:", id)

 
    cursor.execute("""
    SELECT archivo
    FROM materiales
    WHERE id=?
    """, (id,))

    material = cursor.fetchone()

    conn.close()

    return redirect(
        f"/static/materiales/{material[0]}"
    )

# =========================
# RUN
# =========================
if __name__ == '__main__':
    app.run(debug=True)