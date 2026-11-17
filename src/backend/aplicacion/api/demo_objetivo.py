from flask import Blueprint, jsonify, render_template_string, request


bp = Blueprint("demo_objetivo", __name__, url_prefix="/demo-objetivo")


FORMULARIO = """
<!doctype html>
<html lang="es">
<head><meta charset="utf-8"><title>Demo Calidad</title></head>
<body>
<main>
<h1>Inicio de sesion</h1>
<form method="post" action="/demo-objetivo/login">
<label>Correo <input id="correo" name="correo" type="email"></label>
<label>Contrasena <input id="contrasena" name="contrasena" type="password"></label>
<button type="submit">Entrar</button>
</form>
</main>
</body>
</html>
"""


PANEL = """
<!doctype html>
<html lang="es">
<head><meta charset="utf-8"><title>Panel Demo</title></head>
<body>
<main><h1>Panel con fallo conocido</h1><p>Sesion iniciada para demostracion.</p></main>
</body>
</html>
"""


COMPONENTES = """
<!doctype html>
<html lang="es">
<head><meta charset="utf-8"><title>Componentes Demo</title></head>
<body>
<main>
<h1 id="titulo-componentes">Componentes de prueba</h1>
<input id="campo-texto" name="campo_texto" class="campo-demo" data-estado="listo" value="">
<input id="checkbox-demo" type="checkbox">
<select id="select-demo">
<option value="">Seleccione</option>
<option value="uno">Uno</option>
<option value="dos">Dos</option>
</select>
<button id="boton-demo" onclick="document.getElementById('resultado').textContent='Boton presionado'">Presionar</button>
<button id="boton-alerta" onclick="alert('Alerta de prueba')">Mostrar alerta</button>
<a id="enlace-demo" href="/demo-objetivo/componentes?enlace=ok">Enlace completo</a>
<a id="nueva-pestana" target="_blank" href="/demo-objetivo/componentes?tab=nueva">Abrir pestaña</a>
<p id="resultado">Esperando accion</p>
<p id="aparece-tarde" style="display:none">Elemento dinamico listo</p>
<div style="height:900px"></div>
<p id="final-pagina">Final de pagina</p>
<script>
setTimeout(function () {
  document.getElementById('aparece-tarde').style.display = 'block';
}, 300);
</script>
</main>
</body>
</html>
"""


@bp.get("/health")
def health():
    return jsonify({"estado": "disponible"})


@bp.get("/api/estado")
def api_estado():
    fallo = request.args.get("fallo") == "true"
    return jsonify({"servicio": "demo", "correcto": not fallo})


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        return render_template_string(PANEL)
    return render_template_string(FORMULARIO)


@bp.get("/componentes")
def componentes():
    return render_template_string(COMPONENTES)
