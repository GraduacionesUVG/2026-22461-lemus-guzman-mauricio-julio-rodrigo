import hashlib
from functools import partial
from io import BytesIO
from pathlib import Path
from uuid import UUID
from xml.sax.saxutils import escape

from flask import current_app
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import BaseDocTemplate, CondPageBreak, Frame, Image, KeepTogether, PageTemplate, Paragraph, Spacer, Table, TableStyle

from aplicacion.extensiones import db
from aplicacion.modelos import Alerta, CanalNotificacion, Evidencia, Ejecucion, InformeEjecucion, Notificacion, Proyecto, RevisionEjecucion
from aplicacion.servicios.serializacion import serializar_ejecucion
from aplicacion.utilidades.presentacion import duracion_legible, etiqueta_estado, fecha_legible, recortar, resumir_diagnostico
from aplicacion.utilidades.tiempo import ahora_utc


AZUL = colors.HexColor("#132b46")
TURQUESA = colors.HexColor("#0e7c86")
TURQUESA_SUAVE = colors.HexColor("#e8f7f7")
GRIS = colors.HexColor("#f5f7fb")
GRIS_TEXTO = colors.HexColor("#5b6b7c")
BORDE = colors.HexColor("#d7e0e8")
VERDE = colors.HexColor("#14763d")
ROJO = colors.HexColor("#b42318")
AMBAR = colors.HexColor("#b45309")
NEUTRO = colors.HexColor("#516275")

ANCHO_PAGINA, ALTO_PAGINA = A4
MARGEN_HORIZONTAL = 1.5 * cm
ANCHO_UTIL = ANCHO_PAGINA - 2 * MARGEN_HORIZONTAL
ALTO_BANDA = 2.2 * cm

SEVERIDAD_ESTADO = {"error_tecnico": 3, "fallida": 2, "cancelada": 1, "exitosa": 0}
CLAVES_TECNICAS_OMITIDAS = {"diagnostico_error", "estado", "esperado", "obtenido", "fecha_inicio", "fecha_fin", "duracion_milisegundos", "evidencia", "selector", "accion"}

NUMEROS = ["cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez", "once", "doce", "trece", "catorce", "quince", "dieciséis", "diecisiete", "dieciocho", "diecinueve", "veinte"]
ORDINALES = ["", "primer", "segundo", "tercer", "cuarto", "quinto", "sexto", "séptimo", "octavo", "noveno", "décimo", "undécimo", "duodécimo", "decimotercer", "decimocuarto", "decimoquinto", "decimosexto", "decimoséptimo", "decimoctavo", "decimonoveno", "vigésimo"]


def texto(valor) -> str:
    if valor is None or valor == "":
        return "No disponible"
    return str(valor)


def formato_fecha(valor, zona: str) -> str:
    return fecha_legible(valor, zona)


def formato_duracion(ms: int | None) -> str:
    return duracion_legible(ms)


def numero_en_texto(cantidad: int) -> str:
    return NUMEROS[cantidad] if 0 <= cantidad < len(NUMEROS) else str(cantidad)


def ordinal_en_texto(posicion: int) -> str:
    return ORDINALES[posicion] if 0 < posicion < len(ORDINALES) else f"{posicion}.º"


def plural(cantidad: int, singular: str, plural_texto: str) -> str:
    return f"{cantidad} {singular if cantidad == 1 else plural_texto}"


def color_estado(estado: str):
    if estado == "exitosa" or estado == "enviada":
        return VERDE
    if estado == "fallida":
        return ROJO
    if estado == "error_tecnico":
        return AMBAR
    return NEUTRO


def estilo_estado(estado: str):
    return color_estado(estado)


def accion_legible(accion) -> str:
    if not accion:
        return "No disponible"
    return etiqueta_estado(str(accion))


def selector_legible(selector) -> str:
    if not selector:
        return ""
    if isinstance(selector, dict):
        estrategia = selector.get("estrategia") or "selector"
        valor = selector.get("valor") or ""
        return f"{estrategia}: {valor}" if valor else str(estrategia)
    return str(selector)


def parrafo_estilos():
    base = getSampleStyleSheet()
    base.add(ParagraphStyle(name="TituloQA", parent=base["Title"], textColor=AZUL, alignment=TA_CENTER, fontSize=18, leading=22))
    base.add(ParagraphStyle(name="SeccionQA", parent=base["Heading2"], fontName="Helvetica-Bold", textColor=AZUL, fontSize=11.5, leading=14, spaceBefore=12, spaceAfter=6))
    base.add(ParagraphStyle(name="SubseccionQA", parent=base["Heading3"], fontName="Helvetica-Bold", textColor=AZUL, fontSize=9, leading=11, spaceBefore=6, spaceAfter=3))
    base.add(ParagraphStyle(name="PequenoQA", parent=base["BodyText"], fontName="Helvetica", fontSize=7.5, leading=9.5))
    base.add(ParagraphStyle(name="NormalQA", parent=base["BodyText"], fontName="Helvetica", fontSize=8.5, leading=11.5, textColor=colors.HexColor("#14213d")))
    base.add(ParagraphStyle(name="NotaQA", parent=base["BodyText"], fontName="Helvetica-Oblique", fontSize=7.5, leading=9.5, textColor=GRIS_TEXTO))
    base.add(ParagraphStyle(name="CeldaQA", parent=base["BodyText"], fontName="Helvetica", fontSize=7.5, leading=9.5, textColor=colors.HexColor("#14213d")))
    base.add(ParagraphStyle(name="CeldaSecundariaQA", parent=base["BodyText"], fontName="Helvetica", fontSize=6.5, leading=8, textColor=GRIS_TEXTO))
    base.add(ParagraphStyle(name="EncabezadoCeldaQA", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=7, leading=9, textColor=colors.white))
    base.add(ParagraphStyle(name="EtiquetaQA", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=6.5, leading=8, textColor=GRIS_TEXTO))
    base.add(ParagraphStyle(name="ValorQA", parent=base["BodyText"], fontName="Helvetica", fontSize=8.5, leading=10.5, textColor=colors.HexColor("#14213d")))
    base.add(ParagraphStyle(name="CifraQA", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=15, leading=17, alignment=TA_CENTER, textColor=AZUL))
    base.add(ParagraphStyle(name="CifraEtiquetaQA", parent=base["BodyText"], fontName="Helvetica", fontSize=6.5, leading=8, alignment=TA_CENTER, textColor=GRIS_TEXTO))
    base.add(ParagraphStyle(name="TrazaQA", parent=base["BodyText"], fontName="Courier", fontSize=6.5, leading=8.2, textColor=colors.HexColor("#1f2937"), backColor=GRIS, borderColor=BORDE, borderWidth=0.5, borderPadding=5, spaceBefore=4, spaceAfter=8))
    base.add(ParagraphStyle(name="LeyendaQA", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=7.5, leading=9.5, textColor=AZUL, spaceBefore=4, spaceAfter=3))
    return base


def parrafo(valor, estilo) -> Paragraph:
    return Paragraph(escape(str(valor)).replace("\n", "<br/>"), estilo)


def parrafo_estado(estado: str, estilos) -> Paragraph:
    color = color_estado(estado).hexval().replace("0x", "#")
    return Paragraph(f'<font color="{color}"><b>{escape(etiqueta_estado(estado))}</b></font>', estilos["CeldaQA"])


def estilo_tabla_base(encabezado: bool = True, alternar: int = 0) -> list:
    comandos = [
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, BORDE),
        ("BOX", (0, 0), (-1, -1), 0.4, BORDE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]
    if encabezado:
        comandos.extend([("BACKGROUND", (0, 0), (-1, 0), AZUL), ("VALIGN", (0, 0), (-1, 0), "MIDDLE")])
    for fila in range(2 if encabezado else 1, alternar, 2):
        comandos.append(("BACKGROUND", (0, fila), (-1, fila), colors.HexColor("#fafcfe")))
    return comandos


def tabla(datos, anchos=None, encabezado=True):
    estilos = parrafo_estilos()
    celdas = [
        [
            valor if not isinstance(valor, (str, int, float)) else parrafo(valor, estilos["EncabezadoCeldaQA"] if encabezado and indice == 0 else estilos["CeldaQA"])
            for valor in fila
        ]
        for indice, fila in enumerate(datos)
    ]
    resultado = Table(celdas, colWidths=anchos, repeatRows=1 if encabezado else 0, hAlign="LEFT", splitInRow=1)
    resultado.setStyle(TableStyle(estilo_tabla_base(encabezado, len(celdas))))
    return resultado


def tabla_clave_valor(pares: list[tuple[str, object]], estilos, columnas: int = 2) -> Table:
    ancho_par = ANCHO_UTIL / columnas
    filas = []
    for inicio in range(0, len(pares), columnas):
        fila = []
        for etiqueta, valor in pares[inicio:inicio + columnas]:
            contenido = valor if isinstance(valor, Paragraph) else parrafo(texto(valor), estilos["ValorQA"])
            fila.append([parrafo(etiqueta.upper(), estilos["EtiquetaQA"]), contenido])
        while len(fila) < columnas:
            fila.append("")
        filas.append(fila)
    resultado = Table(filas, colWidths=[ancho_par] * columnas, hAlign="LEFT")
    resultado.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, BORDE),
        ("BOX", (0, 0), (-1, -1), 0.4, BORDE),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return resultado


class LienzoInforme(Canvas):
    def __init__(self, *args, identificador: str = "", **kwargs):
        super().__init__(*args, **kwargs)
        self.identificador = identificador
        self.estados_pagina = []

    def showPage(self):
        self.estados_pagina.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self.estados_pagina)
        for estado in self.estados_pagina:
            self.__dict__.update(estado)
            self.dibujar_pie(total)
            super().showPage()
        super().save()

    def dibujar_pie(self, total: int):
        self.saveState()
        self.setStrokeColor(BORDE)
        self.setLineWidth(0.5)
        self.line(MARGEN_HORIZONTAL, 1.25 * cm, ANCHO_PAGINA - MARGEN_HORIZONTAL, 1.25 * cm)
        self.setFont("Helvetica", 7)
        self.setFillColor(GRIS_TEXTO)
        self.drawString(MARGEN_HORIZONTAL, 0.85 * cm, f"Sistema Integral de Calidad Web · Informe de ejecución {self.identificador}")
        self.drawRightString(ANCHO_PAGINA - MARGEN_HORIZONTAL, 0.85 * cm, f"Página {self._pageNumber} de {total}")
        self.restoreState()


def dibujar_banda_principal(lienzo, documento, identificador: str, generado: str):
    lienzo.saveState()
    lienzo.setFillColor(AZUL)
    lienzo.rect(0, ALTO_PAGINA - ALTO_BANDA, ANCHO_PAGINA, ALTO_BANDA, stroke=0, fill=1)
    lienzo.setFillColor(TURQUESA)
    lienzo.rect(0, ALTO_PAGINA - ALTO_BANDA - 0.09 * cm, ANCHO_PAGINA, 0.09 * cm, stroke=0, fill=1)
    lienzo.setFillColor(colors.white)
    lienzo.setFont("Helvetica-Bold", 15)
    lienzo.drawString(MARGEN_HORIZONTAL, ALTO_PAGINA - 1.05 * cm, "Sistema Integral de Calidad Web")
    lienzo.setFont("Helvetica", 9)
    lienzo.setFillColor(colors.HexColor("#cfe3ef"))
    lienzo.drawString(MARGEN_HORIZONTAL, ALTO_PAGINA - 1.62 * cm, "Informe de ejecución y monitoreo")
    lienzo.setFont("Helvetica-Bold", 9)
    lienzo.setFillColor(colors.white)
    lienzo.drawRightString(ANCHO_PAGINA - MARGEN_HORIZONTAL, ALTO_PAGINA - 1.05 * cm, f"Ejecución {identificador}")
    lienzo.setFont("Helvetica", 7.5)
    lienzo.setFillColor(colors.HexColor("#cfe3ef"))
    lienzo.drawRightString(ANCHO_PAGINA - MARGEN_HORIZONTAL, ALTO_PAGINA - 1.62 * cm, f"Generado: {generado}")
    lienzo.restoreState()


def dibujar_encabezado_continuo(lienzo, documento, identificador: str):
    lienzo.saveState()
    lienzo.setFont("Helvetica-Bold", 7.5)
    lienzo.setFillColor(AZUL)
    lienzo.drawString(MARGEN_HORIZONTAL, ALTO_PAGINA - 1.05 * cm, "Sistema Integral de Calidad Web")
    lienzo.setFont("Helvetica", 7.5)
    lienzo.setFillColor(GRIS_TEXTO)
    lienzo.drawRightString(ANCHO_PAGINA - MARGEN_HORIZONTAL, ALTO_PAGINA - 1.05 * cm, f"Informe de ejecución {identificador}")
    lienzo.setStrokeColor(TURQUESA)
    lienzo.setLineWidth(1)
    lienzo.line(MARGEN_HORIZONTAL, ALTO_PAGINA - 1.25 * cm, ANCHO_PAGINA - MARGEN_HORIZONTAL, ALTO_PAGINA - 1.25 * cm)
    lienzo.restoreState()


def pie_pagina(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(GRIS_TEXTO)
    canvas.drawString(MARGEN_HORIZONTAL, 0.85 * cm, "Sistema Integral de Calidad Web")
    canvas.drawRightString(ANCHO_PAGINA - MARGEN_HORIZONTAL, 0.85 * cm, f"Página {doc.page}")
    canvas.restoreState()


def crear_documento(salida: BytesIO, identificador: str, generado: str) -> BaseDocTemplate:
    documento = BaseDocTemplate(
        salida,
        pagesize=A4,
        leftMargin=MARGEN_HORIZONTAL,
        rightMargin=MARGEN_HORIZONTAL,
        topMargin=1.6 * cm,
        bottomMargin=1.6 * cm,
        title=f"Informe de ejecución {identificador}",
        author="Sistema Integral de Calidad Web",
        subject="Informe de ejecución y monitoreo",
    )
    marco_inicial = Frame(MARGEN_HORIZONTAL, 1.6 * cm, ANCHO_UTIL, ALTO_PAGINA - ALTO_BANDA - 0.7 * cm - 1.6 * cm, id="inicial", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    marco_continuo = Frame(MARGEN_HORIZONTAL, 1.6 * cm, ANCHO_UTIL, ALTO_PAGINA - 1.6 * cm - 1.6 * cm, id="continuo", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    documento.addPageTemplates([
        PageTemplate(id="inicial", frames=[marco_inicial], onPage=partial(dibujar_banda_principal, identificador=identificador, generado=generado), autoNextPageTemplate="continuo"),
        PageTemplate(id="continuo", frames=[marco_continuo], onPage=partial(dibujar_encabezado_continuo, identificador=identificador)),
    ])
    return documento


def resumen_datos(ejecucion: Ejecucion) -> dict:
    resultados = list(ejecucion.resultados)
    alertas = Alerta.query.filter_by(ejecucion_id=ejecucion.id).all()
    notificaciones = Notificacion.query.filter_by(ejecucion_id=ejecucion.id).all()
    evidencias = Evidencia.query.filter_by(ejecucion_id=ejecucion.id).all()
    return {
        "total": len(resultados),
        "exitosos": sum(1 for r in resultados if r.estado == "exitosa"),
        "fallidos": sum(1 for r in resultados if r.estado == "fallida"),
        "errores": sum(1 for r in resultados if r.estado == "error_tecnico"),
        "funcionales": sum(1 for r in resultados if r.tipo == "caso_prueba"),
        "monitores": sum(1 for r in resultados if r.tipo.startswith("monitor")),
        "alertas": len(alertas),
        "alertas_pendientes": sum(1 for a in alertas if a.estado_revision == "pendiente"),
        "notificaciones_registradas": len(notificaciones),
        "notificaciones_enviadas": sum(1 for n in notificaciones if n.estado == "enviada"),
        "notificaciones_fallidas": sum(1 for n in notificaciones if n.estado == "fallida"),
        "evidencias": len(evidencias),
    }


def nombre_grupo(resultado: dict) -> str:
    contexto = resultado.get("contexto") or {}
    return texto(contexto.get("caso_prueba") or contexto.get("monitor") or contexto.get("paso_pipeline") or etiqueta_estado(resultado.get("tipo")))


def nombre_paso(resultado: dict) -> str:
    contexto = resultado.get("contexto") or {}
    return texto(contexto.get("paso_prueba") or contexto.get("paso_pipeline") or etiqueta_estado(resultado.get("tipo")))


def agrupar_por_caso(resultados: list[dict]) -> list[dict]:
    grupos: dict[str, dict] = {}
    for posicion, resultado in enumerate(resultados, start=1):
        clave = nombre_grupo(resultado)
        grupo = grupos.setdefault(clave, {"nombre": clave, "pasos": [], "duracion": 0})
        grupo["pasos"].append((posicion, resultado))
        grupo["duracion"] += int(resultado.get("duracion_milisegundos") or 0)
    for grupo in grupos.values():
        estados = [resultado.get("estado") for _, resultado in grupo["pasos"]]
        grupo["estado"] = max(estados, key=lambda estado: SEVERIDAD_ESTADO.get(estado, 1))
    return list(grupos.values())


def diagnostico_grupo(grupo: dict) -> str:
    pasos = grupo["pasos"]
    exitosos = sum(1 for _, resultado in pasos if resultado.get("estado") == "exitosa")
    if exitosos == len(pasos):
        base = "El paso finalizó correctamente." if len(pasos) == 1 else f"Los {len(pasos)} pasos finalizaron correctamente."
    else:
        base = f"{exitosos} de {plural(len(pasos), 'paso exitoso', 'pasos exitosos')}."
    incidencias = [
        f"{etiqueta_estado(resultado.get('estado'))} en el paso {posicion} ({nombre_paso(resultado)})."
        for posicion, resultado in pasos
        if resultado.get("estado") != "exitosa"
    ]
    return " ".join([base, *incidencias[:3]])


def observacion_paso(resultado: dict, referencia: str | None) -> str:
    mensaje = resultado.get("mensaje") or ""
    if resultado.get("estado") == "exitosa":
        return recortar(mensaje, 160) or "Sin observaciones."
    resumen = resumir_diagnostico(mensaje)
    if resumen:
        return f"{resumen} Ver {referencia}." if referencia else resumen
    if referencia:
        return f"El registro original no incluye una descripción del error. Ver {referencia}."
    return "El registro original no incluye una descripción del error."


def bloque_identificacion(ejecucion: Ejecucion, datos: dict, proyecto, zona: str, estilos):
    pares = [
        ("Proyecto", texto(datos.get("proyecto_nombre"))),
        ("Pipeline", texto(datos.get("pipeline_nombre"))),
        ("Entorno", texto(datos.get("entorno_nombre"))),
        ("Identificador", str(ejecucion.id)),
        ("Inicio", formato_fecha(ejecucion.fecha_inicio, zona)),
        ("Finalización", formato_fecha(ejecucion.fecha_fin, zona)),
        ("Duración total", formato_duracion(ejecucion.duracion_milisegundos)),
        ("Estado final", parrafo_estado(ejecucion.estado, estilos)),
        ("Solicitud", formato_fecha(ejecucion.fecha_encolado, zona)),
        ("Origen", etiqueta_estado(ejecucion.origen)),
    ]
    if proyecto and proyecto.responsable:
        pares.append(("Responsable", proyecto.responsable))
    pares.append(("Zona horaria", zona))
    return tabla_clave_valor(pares, estilos, columnas=2)


def banda_estado(ejecucion: Ejecucion, resumen: dict, estilos) -> Table:
    color = color_estado(ejecucion.estado)
    mensajes = {
        "exitosa": "Todos los pasos registrados finalizaron correctamente.",
        "fallida": "Uno o más pasos no cumplieron el resultado esperado.",
        "error_tecnico": "La automatización no pudo completar al menos una acción. Un error técnico no confirma por sí mismo un defecto del sistema evaluado.",
    }
    explicacion = mensajes.get(ejecucion.estado, f"La ejecución finalizó con estado {etiqueta_estado(ejecucion.estado).lower()}.")
    estilo_titulo = ParagraphStyle("BandaTitulo", parent=estilos["NormalQA"], fontName="Helvetica-Bold", fontSize=10, leading=12, textColor=color)
    contenido = [
        Paragraph(f"Estado final: {escape(etiqueta_estado(ejecucion.estado))}", estilo_titulo),
        parrafo(explicacion, estilos["NormalQA"]),
    ]
    banda = Table([[contenido]], colWidths=[ANCHO_UTIL])
    banda.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GRIS),
        ("LINEBEFORE", (0, 0), (0, -1), 3, color),
        ("BOX", (0, 0), (-1, -1), 0.4, BORDE),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return banda


def mosaico_indicadores(resumen: dict, estilos) -> Table:
    if resumen["notificaciones_registradas"]:
        notificaciones = f"{resumen['notificaciones_enviadas']} / {resumen['notificaciones_fallidas']}"
        etiqueta_notificaciones = "Notificaciones enviadas / fallidas"
    else:
        notificaciones = "—"
        etiqueta_notificaciones = "Notificaciones (sin registro)"
    indicadores = [
        (str(resumen["total"]), "Pasos ejecutados", AZUL),
        (str(resumen["exitosos"]), "Exitosos", VERDE),
        (str(resumen["fallidos"]), "Fallidos", ROJO),
        (str(resumen["errores"]), "Errores técnicos", AMBAR),
        (str(resumen["evidencias"]), "Evidencias", AZUL),
        (str(resumen["alertas"]), "Alertas", AZUL),
        (notificaciones, etiqueta_notificaciones, AZUL),
    ]
    celdas = []
    for valor, etiqueta, color in indicadores:
        estilo_cifra = ParagraphStyle(f"Cifra{etiqueta}", parent=estilos["CifraQA"], textColor=color)
        celdas.append([Paragraph(escape(valor), estilo_cifra), parrafo(etiqueta, estilos["CifraEtiquetaQA"])])
    mosaico = Table([celdas], colWidths=[ANCHO_UTIL / len(indicadores)] * len(indicadores))
    comandos = [
        ("BOX", (0, 0), (-1, -1), 0.4, BORDE),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDE),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    for columna, (_, _, color) in enumerate(indicadores):
        comandos.append(("LINEABOVE", (columna, 0), (columna, 0), 2, color))
    mosaico.setStyle(TableStyle(comandos))
    return mosaico


def tabla_casos(grupos: list[dict], estilos) -> Table:
    filas = [["Caso de prueba o monitor", "Resultado", "Pasos", "Duración", "Resumen del diagnóstico"]]
    for grupo in grupos:
        filas.append([
            parrafo(grupo["nombre"], estilos["CeldaQA"]),
            parrafo_estado(grupo["estado"], estilos),
            parrafo(str(len(grupo["pasos"])), estilos["CeldaQA"]),
            parrafo(formato_duracion(grupo["duracion"]), estilos["CeldaQA"]),
            parrafo(diagnostico_grupo(grupo), estilos["CeldaQA"]),
        ])
    return tabla(filas, [5.2 * cm, 2.2 * cm, 1.2 * cm, 1.8 * cm, ANCHO_UTIL - 10.4 * cm])


def tabla_pasos(resultados: list[dict], referencias: dict, estilos) -> Table:
    filas = [["#", "Paso", "Acción", "Resultado", "Duración", "Observación"]]
    for posicion, resultado in enumerate(resultados, start=1):
        contexto = resultado.get("contexto") or {}
        selector = selector_legible(contexto.get("selector"))
        celda_paso = [parrafo(nombre_paso(resultado), estilos["CeldaQA"])]
        if selector:
            celda_paso.append(parrafo(recortar(selector, 90), estilos["CeldaSecundariaQA"]))
        filas.append([
            parrafo(str(posicion), estilos["CeldaQA"]),
            celda_paso,
            parrafo(accion_legible(contexto.get("accion") or resultado.get("tipo")), estilos["CeldaQA"]),
            parrafo_estado(resultado.get("estado"), estilos),
            parrafo(formato_duracion(resultado.get("duracion_milisegundos")), estilos["CeldaQA"]),
            parrafo(observacion_paso(resultado, referencias.get(resultado.get("id"))), estilos["CeldaQA"]),
        ])
    return tabla(filas, [0.7 * cm, 5.2 * cm, 2.5 * cm, 2 * cm, 1.6 * cm, ANCHO_UTIL - 12 * cm])


def seccion_incidencias(ejecucion: Ejecucion, incidencias: list[tuple[int, dict]], referencias: dict, estilos) -> list:
    contenido = []
    for posicion, resultado in incidencias:
        contexto = resultado.get("contexto") or {}
        tecnicos = resultado.get("datos_tecnicos_sanitizados") or {}
        resumen = resumir_diagnostico(resultado.get("mensaje"))
        pares = [
            ("Paso afectado", f"{posicion}. {nombre_paso(resultado)}"),
            ("Acción", accion_legible(contexto.get("accion") or resultado.get("tipo"))),
            ("Estado", parrafo_estado(resultado.get("estado"), estilos)),
            ("Caso o monitor", nombre_grupo(resultado)),
            ("Selector", selector_legible(contexto.get("selector")) or "No aplica"),
            ("URL al momento del paso", tecnicos.get("url_actual") or "No disponible"),
            ("Resultado esperado", resultado.get("esperado") or "No registrado"),
            ("Resultado obtenido", resultado.get("obtenido") or "No registrado"),
            ("Diagnóstico resumido", resumen or "El registro original no incluye una descripción del error."),
            ("Detalle técnico", f"Consulte {referencias.get(resultado.get('id'))}." if referencias.get(resultado.get("id")) else "No hay traza técnica registrada."),
        ]
        contenido.append(KeepTogether([
            parrafo(f"Paso {posicion} · {etiqueta_estado(resultado.get('estado'))}", estilos["SubseccionQA"]),
            tabla_clave_valor(pares, estilos, columnas=2),
            Spacer(1, 0.2 * cm),
        ]))
    if ejecucion.error_tecnico:
        contenido.append(KeepTogether([
            parrafo("Error técnico de la ejecución", estilos["SubseccionQA"]),
            tabla_clave_valor([
                ("Diagnóstico resumido", resumir_diagnostico(ejecucion.error_tecnico) or "El registro original no incluye una descripción del error."),
                ("Detalle técnico", f"Consulte {referencias.get('ejecucion')}."),
            ], estilos, columnas=2),
        ]))
    return contenido


def tabla_alertas(alertas: list, zona: str, estilos) -> Table:
    filas = [["Tipo", "Detección", "Severidad", "Revisión", "Clasificación", "Observación"]]
    for alerta in alertas:
        filas.append([
            parrafo(etiqueta_estado(alerta.tipo), estilos["CeldaQA"]),
            parrafo(formato_fecha(alerta.fecha_deteccion, zona), estilos["CeldaQA"]),
            parrafo(etiqueta_estado(alerta.severidad), estilos["CeldaQA"]),
            parrafo(etiqueta_estado(alerta.estado_revision), estilos["CeldaQA"]),
            parrafo(etiqueta_estado(alerta.clasificacion_manual), estilos["CeldaQA"]),
            parrafo(alerta.observacion_revision or "Sin observaciones.", estilos["CeldaQA"]),
        ])
    return tabla(filas, [2.2 * cm, 3.9 * cm, 1.7 * cm, 2 * cm, 2.6 * cm, ANCHO_UTIL - 12.4 * cm])


def tabla_notificaciones(notificaciones: list, zona: str, estilos) -> Table:
    filas = [["Canal", "Tipo", "Estado", "Intentos", "Fecha", "Observación"]]
    for notificacion in notificaciones:
        canal = db.session.get(CanalNotificacion, notificacion.canal_notificacion_id) if notificacion.canal_notificacion_id else None
        filas.append([
            parrafo(canal.nombre if canal else "Sin canal", estilos["CeldaQA"]),
            parrafo(etiqueta_estado(canal.tipo) if canal else "No aplica", estilos["CeldaQA"]),
            parrafo_estado(notificacion.estado, estilos),
            parrafo(str(notificacion.intentos), estilos["CeldaQA"]),
            parrafo(formato_fecha(notificacion.fecha_envio or notificacion.fecha_solicitud, zona), estilos["CeldaQA"]),
            parrafo(notificacion.error_sanitizado or "Sin observaciones.", estilos["CeldaQA"]),
        ])
    return tabla(filas, [2.8 * cm, 1.7 * cm, 1.7 * cm, 1.4 * cm, 3.9 * cm, ANCHO_UTIL - 11.5 * cm])


def bloque_evidencia(evidencia, numero: int, pasos_por_id: dict, raiz: Path, estilos) -> KeepTogether:
    paso = pasos_por_id.get(str(evidencia.resultado_paso_id)) if evidencia.resultado_paso_id else None
    titulo = f"Figura {numero}. " + (f"Paso {paso[0]} · {nombre_paso(paso[1])}" if paso else "Evidencia de la ejecución") + f" — {evidencia.nombre_archivo}"
    elementos = [parrafo(titulo, estilos["LeyendaQA"])]
    ruta_imagen = raiz / evidencia.ruta_relativa
    if ruta_imagen.exists() and (evidencia.tipo_contenido or "").startswith("image"):
        imagen = Image(str(ruta_imagen))
        escala = min(ANCHO_UTIL / imagen.imageWidth, 11.5 * cm / imagen.imageHeight, 1)
        imagen.drawWidth = imagen.imageWidth * escala
        imagen.drawHeight = imagen.imageHeight * escala
        imagen.hAlign = "LEFT"
        marco = Table([[imagen]], colWidths=[imagen.drawWidth + 2])
        marco.hAlign = "LEFT"
        marco.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, BORDE), ("LEFTPADDING", (0, 0), (-1, -1), 1), ("RIGHTPADDING", (0, 0), (-1, -1), 1), ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
        elementos.append(marco)
    elif ruta_imagen.exists():
        elementos.append(parrafo(f"Archivo disponible en la plataforma ({evidencia.tipo_contenido}).", estilos["NotaQA"]))
    else:
        elementos.append(parrafo("Imagen no disponible en almacenamiento.", estilos["NotaQA"]))
    elementos.append(Spacer(1, 0.3 * cm))
    return KeepTogether(elementos)


def conclusiones(ejecucion: Ejecucion, resumen: dict) -> list[str]:
    total = resumen["total"]
    exitosos = resumen["exitosos"]
    resultados = list(ejecucion.resultados)
    posiciones_error = [indice for indice, resultado in enumerate(resultados, start=1) if resultado.estado == "error_tecnico"]
    posiciones_fallo = [indice for indice, resultado in enumerate(resultados, start=1) if resultado.estado == "fallida"]
    partes = []
    if total == 0:
        partes.append(f"La ejecución finalizó con estado {etiqueta_estado(ejecucion.estado).lower()} y no registró resultados de pasos; el diagnóstico técnico disponible se incluye en el anexo.")
    elif ejecucion.estado == "exitosa":
        partes.append(f"La ejecución finalizó de forma exitosa. Se completaron satisfactoriamente los {numero_en_texto(total)} pasos registrados." if total > 1 else "La ejecución finalizó de forma exitosa. El paso registrado se completó satisfactoriamente.")
    else:
        apertura = {
            "error_tecnico": "La ejecución finalizó con un error técnico.",
            "fallida": "La ejecución finalizó con resultado fallido.",
        }.get(ejecucion.estado, f"La ejecución finalizó con estado {etiqueta_estado(ejecucion.estado).lower()}.")
        detalle = f"Se completaron satisfactoriamente {numero_en_texto(exitosos)} de los {numero_en_texto(total)} pasos registrados"
        incidencias = []
        if posiciones_fallo:
            descripcion = f"el {ordinal_en_texto(posiciones_fallo[0])} paso" if len(posiciones_fallo) == 1 else f"{numero_en_texto(len(posiciones_fallo))} pasos"
            incidencias.append(f"{descripcion} no cumplió el resultado esperado" if len(posiciones_fallo) == 1 else f"{descripcion} no cumplieron el resultado esperado")
        if posiciones_error:
            descripcion = f"durante el {ordinal_en_texto(posiciones_error[0])} paso" if len(posiciones_error) == 1 else f"en {numero_en_texto(len(posiciones_error))} pasos"
            incidencias.append(f"se presentó una dificultad técnica {descripcion}")
        if incidencias:
            detalle += " y " + " y ".join(incidencias)
        partes.append(f"{apertura} {detalle}.")
        if posiciones_error:
            partes.append("Un error técnico indica que la automatización no pudo completar la acción y no constituye por sí mismo la confirmación de un defecto en el sistema evaluado.")
    if resumen["evidencias"]:
        partes.append("Se conservó evidencia visual para su revisión." if resumen["evidencias"] == 1 else f"Se conservaron {numero_en_texto(resumen['evidencias'])} evidencias visuales para su revisión.")
    if resumen["alertas"]:
        pendientes = resumen.get("alertas_pendientes", 0)
        texto_alertas = "Se generó una alerta" if resumen["alertas"] == 1 else f"Se generaron {numero_en_texto(resumen['alertas'])} alertas"
        if pendientes:
            texto_alertas += ", pendiente de revisión humana" if resumen["alertas"] == 1 else f", de las cuales {numero_en_texto(pendientes)} {'está pendiente' if pendientes == 1 else 'están pendientes'} de revisión humana"
        partes.append(f"{texto_alertas}.")
    if ejecucion.pipeline and "fallos controlados" in ejecucion.pipeline.nombre.lower():
        partes.append("Los fallos del pipeline corresponden a pruebas deliberadas de detección; se conserva el estado técnico registrado.")
    return [" ".join(partes)]


def titulo_referencia(referencia: str) -> str:
    return referencia[:1].upper() + referencia[1:]


def compactar_espacios(valor) -> str:
    return " ".join(str(valor).split())


def seccion_anexo(ejecucion: Ejecucion, incidencias: list[tuple[int, dict]], referencias: dict, estilos) -> list:
    contenido = []
    for posicion, resultado in incidencias:
        referencia = referencias.get(resultado.get("id"))
        if not referencia:
            continue
        contenido.append(parrafo(f"{titulo_referencia(referencia)} · Paso {posicion}: {nombre_paso(resultado)}", estilos["SubseccionQA"]))
        traza = resultado.get("mensaje") or "Sin traza registrada."
        contenido.append(parrafo(traza, estilos["TrazaQA"]))
        tecnicos = resultado.get("datos_tecnicos_sanitizados") or {}
        diagnostico_error = tecnicos.get("diagnostico_error")
        if diagnostico_error and str(diagnostico_error).strip() != str(resultado.get("mensaje") or "").strip():
            contenido.append(parrafo("Diagnóstico registrado por el motor de automatización:", estilos["NotaQA"]))
            contenido.append(parrafo(diagnostico_error, estilos["TrazaQA"]))
        metadatos = [(clave, valor) for clave, valor in tecnicos.items() if clave not in CLAVES_TECNICAS_OMITIDAS and valor not in (None, "", "None")]
        if metadatos:
            filas = [["Metadato", "Valor registrado"]]
            filas.extend([[clave.replace("_", " ").capitalize(), recortar(compactar_espacios(valor), 600)] for clave, valor in metadatos])
            contenido.append(tabla(filas, [4.2 * cm, ANCHO_UTIL - 4.2 * cm]))
            contenido.append(Spacer(1, 0.25 * cm))
    if ejecucion.error_tecnico and referencias.get("ejecucion"):
        contenido.append(parrafo(f"{titulo_referencia(referencias['ejecucion'])} · Error técnico de la ejecución", estilos["SubseccionQA"]))
        contenido.append(parrafo(ejecucion.error_tecnico, estilos["TrazaQA"]))
    return contenido


def ruta_informe(nombre: str) -> Path:
    raiz = Path(current_app.config["RUTA_INFORMES"])
    raiz.mkdir(parents=True, exist_ok=True)
    return raiz / nombre


def obtener_o_generar_informe(ejecucion_id: UUID, regenerar: bool = False) -> InformeEjecucion:
    ejecucion = Ejecucion.query.get_or_404(ejecucion_id)
    existente = InformeEjecucion.query.filter_by(ejecucion_id=ejecucion.id).order_by(InformeEjecucion.generado_en.desc()).first()
    if existente and not regenerar:
        ruta = Path(current_app.config["RUTA_INFORMES"]) / existente.ruta_relativa
        if ruta.is_file():
            contenido = ruta.read_bytes()
            if contenido.startswith(b"%PDF-") and hashlib.sha256(contenido).hexdigest() == existente.hash_sha256:
                return existente
    return generar_informe(ejecucion)


def construir_pdf_informe(ejecucion: Ejecucion) -> bytes:
    zona = current_app.config.get("ZONA_HORARIA_APLICACION", "America/Guatemala")
    identificador = str(ejecucion.id)[:8]
    estilos = parrafo_estilos()
    salida = BytesIO()
    documento = crear_documento(salida, identificador, formato_fecha(ahora_utc(), zona))
    datos = serializar_ejecucion(ejecucion)
    resultados = datos["resultados"]
    resumen = resumen_datos(ejecucion)
    revision = RevisionEjecucion.query.filter_by(ejecucion_id=ejecucion.id).order_by(RevisionEjecucion.actualizado_en.desc()).first()
    proyecto = db.session.get(Proyecto, ejecucion.pipeline.proyecto_id) if ejecucion.pipeline else None
    incidencias = [(posicion, resultado) for posicion, resultado in enumerate(resultados, start=1) if resultado.get("estado") != "exitosa"]
    referencias = {}
    for indice, (_, resultado) in enumerate(incidencias, start=1):
        if resultado.get("mensaje") or (resultado.get("datos_tecnicos_sanitizados") or {}).get("diagnostico_error"):
            referencias[resultado.get("id")] = f"anexo A.{indice}"
    if ejecucion.error_tecnico:
        referencias["ejecucion"] = f"anexo A.{len(incidencias) + 1}"
    numero_seccion = 0

    def seccion(titulo: str) -> list:
        nonlocal numero_seccion
        numero_seccion += 1
        return [CondPageBreak(2.5 * cm), parrafo(f"{numero_seccion}. {titulo}", estilos["SeccionQA"])]

    story = [bloque_identificacion(ejecucion, datos, proyecto, zona, estilos)]

    story.extend(seccion("Resumen ejecutivo"))
    story.append(banda_estado(ejecucion, resumen, estilos))
    story.append(Spacer(1, 0.2 * cm))
    story.append(mosaico_indicadores(resumen, estilos))
    revision_texto = etiqueta_estado(revision.clasificacion) if revision else ("Pendiente" if datos.get("requiere_revision_humana") else "No requerida")
    story.append(Spacer(1, 0.15 * cm))
    story.append(parrafo(f"Pruebas funcionales: {resumen['funcionales']} pasos · Monitores evaluados: {resumen['monitores']} · Revisión humana: {revision_texto}", estilos["NotaQA"]))
    if not resumen["notificaciones_registradas"]:
        story.append(parrafo("No había notificaciones registradas al generar este informe. En el flujo automático el informe se genera antes del envío para adjuntarse al mensaje; el resultado de la entrega queda registrado en la plataforma.", estilos["NotaQA"]))

    if resultados:
        story.extend(seccion("Resumen por caso de prueba"))
        story.append(tabla_casos(agrupar_por_caso(resultados), estilos))
        story.extend(seccion("Detalle de pasos"))
        story.append(tabla_pasos(resultados, referencias, estilos))

    if incidencias or ejecucion.error_tecnico:
        story.extend(seccion("Errores técnicos y fallos"))
        story.extend(seccion_incidencias(ejecucion, incidencias, referencias, estilos))

    alertas = Alerta.query.filter_by(ejecucion_id=ejecucion.id).order_by(Alerta.fecha_deteccion.asc()).all()
    notificaciones = Notificacion.query.filter_by(ejecucion_id=ejecucion.id).order_by(Notificacion.fecha_solicitud.asc()).all()
    story.extend(seccion("Alertas y notificaciones"))
    if alertas:
        story.append(tabla_alertas(alertas, zona, estilos))
    else:
        story.append(parrafo("La ejecución no generó alertas.", estilos["NotaQA"]))
    story.append(Spacer(1, 0.2 * cm))
    if notificaciones:
        story.append(tabla_notificaciones(notificaciones, zona, estilos))
    else:
        story.append(parrafo("Sin notificaciones registradas al momento de generar el informe.", estilos["NotaQA"]))

    evidencias = Evidencia.query.filter_by(ejecucion_id=ejecucion.id).order_by(Evidencia.creado_en.asc()).all()
    if evidencias:
        story.extend(seccion("Evidencias visuales"))
        raiz = Path(current_app.config["RUTA_EVIDENCIAS"])
        pasos_por_id = {str(resultado.get("id")): (posicion, resultado) for posicion, resultado in enumerate(resultados, start=1)}
        for numero, evidencia in enumerate(evidencias, start=1):
            story.append(bloque_evidencia(evidencia, numero, pasos_por_id, raiz, estilos))

    story.extend(seccion("Conclusión"))
    for linea in conclusiones(ejecucion, resumen):
        story.append(parrafo(linea, estilos["NormalQA"]))

    anexo = seccion_anexo(ejecucion, incidencias, referencias, estilos)
    if anexo:
        story.append(CondPageBreak(4 * cm))
        story.append(parrafo("Anexo técnico", estilos["SeccionQA"]))
        story.append(parrafo("Trazas y metadatos sanitizados tal como fueron registrados por el motor de ejecución.", estilos["NotaQA"]))
        story.extend(anexo)

    documento.build(story, canvasmaker=partial(LienzoInforme, identificador=identificador))
    return salida.getvalue()


def generar_informe(ejecucion: Ejecucion) -> InformeEjecucion:
    zona = current_app.config.get("ZONA_HORARIA_APLICACION", "America/Guatemala")
    nombre = f"informe_ejecucion_{str(ejecucion.id)[:8]}.pdf"
    ruta = ruta_informe(nombre)
    contenido = construir_pdf_informe(ejecucion)
    ruta_temporal = ruta.with_suffix(".pdf.tmp")
    ruta_temporal.write_bytes(contenido)
    ruta_temporal.replace(ruta)
    informe = InformeEjecucion.query.filter_by(ejecucion_id=ejecucion.id).first()
    if informe is None:
        informe = InformeEjecucion(ejecucion_id=ejecucion.id)
        db.session.add(informe)
    informe.ruta_relativa = nombre
    informe.nombre_archivo = nombre
    informe.tipo_contenido = "application/pdf"
    informe.tamano_bytes = len(contenido)
    informe.hash_sha256 = hashlib.sha256(contenido).hexdigest()
    informe.zona_horaria = zona
    informe.version = (informe.version or 0) + 1
    db.session.commit()
    return informe
