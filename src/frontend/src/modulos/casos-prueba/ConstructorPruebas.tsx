import { ArrowDown, ArrowUp, ChevronDown, ChevronRight, Copy, Plus, Trash2 } from "lucide-react";
import { ChangeEvent, useEffect, useMemo, useState } from "react";
import { solicitar } from "../../api/cliente";
import { MarcoModulo } from "../../componentes/MarcoModulo";
import { CasoPrueba, PasoCasoPrueba, Proyecto, RespuestaLista, Secreto } from "../../tipos/dominio";
import { useAvisos } from "../../componentes/Avisos";

type SelectorConfig = {
  estrategia?: string;
  valor?: string;
};

type ConfiguracionPaso = Record<string, unknown> & {
  selector?: SelectorConfig;
};

const estrategiasSelector = [
  ["id", "ID"],
  ["name", "Name"],
  ["css", "CSS"],
  ["xpath", "XPath"],
  ["texto", "Texto visible"],
  ["tag_name", "Etiqueta"],
  ["class_name", "Clase"],
  ["link_text", "Texto de enlace"],
  ["partial_link_text", "Texto parcial de enlace"]
];

const teclasPermitidas = ["ENTER", "TAB", "ESCAPE", "SPACE", "BACKSPACE", "DELETE", "ARROW_UP", "ARROW_DOWN", "ARROW_LEFT", "ARROW_RIGHT", "HOME", "END", "PAGE_UP", "PAGE_DOWN"];

const acciones: Array<{ categoria: string; opciones: Array<{ valor: PasoCasoPrueba["tipo"]; etiqueta: string }> }> = [
  { categoria: "Navegación", opciones: [
    { valor: "navegar", etiqueta: "Navegar" },
    { valor: "retroceder", etiqueta: "Retroceder" },
    { valor: "avanzar", etiqueta: "Avanzar" },
    { valor: "recargar", etiqueta: "Recargar" }
  ] },
  { categoria: "Elementos", opciones: [
    { valor: "escribir", etiqueta: "Escribir" },
    { valor: "limpiar_campo", etiqueta: "Limpiar campo" },
    { valor: "hacer_clic", etiqueta: "Hacer clic" },
    { valor: "doble_clic", etiqueta: "Doble clic" },
    { valor: "clic_derecho", etiqueta: "Clic derecho" },
    { valor: "mover_mouse", etiqueta: "Mover mouse" },
    { valor: "seleccionar_opcion", etiqueta: "Seleccionar opción" },
    { valor: "marcar_checkbox", etiqueta: "Marcar checkbox" },
    { valor: "desmarcar_checkbox", etiqueta: "Desmarcar checkbox" },
    { valor: "presionar_tecla", etiqueta: "Presionar tecla" },
    { valor: "scroll", etiqueta: "Scroll" }
  ] },
  { categoria: "Esperas", opciones: [
    { valor: "esperar_elemento", etiqueta: "Esperar elemento" },
    { valor: "esperar_texto", etiqueta: "Esperar texto" },
    { valor: "esperar_url", etiqueta: "Esperar URL" }
  ] },
  { categoria: "Validaciones", opciones: [
    { valor: "validar_texto", etiqueta: "Validar texto" },
    { valor: "validar_elemento_visible", etiqueta: "Validar visible" },
    { valor: "validar_elemento_existente", etiqueta: "Validar existencia" },
    { valor: "validar_elemento_habilitado", etiqueta: "Validar habilitado" },
    { valor: "validar_elemento_seleccionado", etiqueta: "Validar seleccionado" },
    { valor: "validar_atributo", etiqueta: "Validar atributo" },
    { valor: "validar_url", etiqueta: "Validar URL" },
    { valor: "validar_titulo", etiqueta: "Validar título" }
  ] },
  { categoria: "Alertas", opciones: [
    { valor: "aceptar_alerta", etiqueta: "Aceptar alerta" },
    { valor: "cancelar_alerta", etiqueta: "Cancelar alerta" },
    { valor: "validar_texto_alerta", etiqueta: "Validar texto de alerta" }
  ] },
  { categoria: "Ventanas", opciones: [
    { valor: "cambiar_a_nueva_pestana", etiqueta: "Cambiar a nueva pestaña" },
    { valor: "cambiar_a_pestana", etiqueta: "Cambiar a pestaña" },
    { valor: "cerrar_pestana", etiqueta: "Cerrar pestaña" }
  ] },
  { categoria: "Evidencia", opciones: [
    { valor: "capturar_evidencia", etiqueta: "Capturar evidencia" }
  ] }
];

const tiposConSelector = new Set<PasoCasoPrueba["tipo"]>([
  "escribir",
  "limpiar_campo",
  "hacer_clic",
  "doble_clic",
  "clic_derecho",
  "mover_mouse",
  "seleccionar_opcion",
  "marcar_checkbox",
  "desmarcar_checkbox",
  "esperar_elemento",
  "esperar_texto",
  "validar_texto",
  "validar_elemento_visible",
  "validar_elemento_existente",
  "validar_elemento_habilitado",
  "validar_elemento_seleccionado",
  "validar_atributo"
]);

function configuracionInicial(tipo: PasoCasoPrueba["tipo"]): ConfiguracionPaso {
  const selector = { estrategia: "css", valor: "" };
  const mapa: Record<PasoCasoPrueba["tipo"], ConfiguracionPaso> = {
    navegar: { ruta_o_url: "/login" },
    retroceder: {},
    avanzar: {},
    recargar: {},
    escribir: { selector: { estrategia: "id", valor: "correo" }, origen_valor: "texto", texto: "demo@example.com" },
    limpiar_campo: { selector },
    hacer_clic: { selector: { estrategia: "css", valor: "button[type='submit']" } },
    doble_clic: { selector },
    clic_derecho: { selector },
    mover_mouse: { selector },
    seleccionar_opcion: { selector: { estrategia: "id", valor: "select-demo" }, metodo: "valor", valor: "uno" },
    marcar_checkbox: { selector: { estrategia: "id", valor: "checkbox-demo" } },
    desmarcar_checkbox: { selector: { estrategia: "id", valor: "checkbox-demo" } },
    presionar_tecla: { usar_selector: false, selector: { estrategia: "id", valor: "" }, tecla: "ENTER" },
    scroll: { modalidad: "abajo", selector: { estrategia: "id", valor: "" } },
    esperar_elemento: { selector, condicion: "visible", timeout_segundos: 10 },
    esperar_texto: { selector, texto_esperado: "", timeout_segundos: 10 },
    esperar_url: { texto_url: "", comparacion: "contiene", timeout_segundos: 10 },
    validar_texto: { selector: { estrategia: "css", valor: "main h1" }, texto_esperado: "Panel principal", comparacion: "contiene" },
    validar_elemento_visible: { selector },
    validar_elemento_existente: { selector },
    validar_elemento_habilitado: { selector },
    validar_elemento_seleccionado: { selector },
    validar_atributo: { selector, atributo: "data-estado", valor_esperado: "listo", comparacion: "igual" },
    validar_url: { url_esperada: "", comparacion: "contiene" },
    validar_titulo: { titulo_esperado: "", comparacion: "contiene" },
    aceptar_alerta: {},
    cancelar_alerta: {},
    validar_texto_alerta: { texto_esperado: "", comparacion: "contiene" },
    cambiar_a_nueva_pestana: {},
    cambiar_a_pestana: { indice: 0 },
    cerrar_pestana: {},
    capturar_evidencia: { nombre: "captura_manual" }
  };
  return mapa[tipo];
}

function nombreInicial(tipo: PasoCasoPrueba["tipo"]) {
  const opcion = acciones.flatMap((grupo) => grupo.opciones).find((item) => item.valor === tipo);
  return opcion?.etiqueta ?? tipo;
}

function crearPaso(orden: number, tipo: PasoCasoPrueba["tipo"] = "navegar"): PasoCasoPrueba {
  return { orden, tipo, nombre: nombreInicial(tipo), configuracion: configuracionInicial(tipo), continuar_si_falla: false, capturar_evidencia: true };
}

function normalizarOrden(pasos: PasoCasoPrueba[]) {
  return pasos.map((paso, indice) => ({ ...paso, orden: indice + 1 }));
}

function texto(valor: unknown) {
  return typeof valor === "string" ? valor : "";
}

function numero(valor: unknown, predeterminado: number) {
  return typeof valor === "number" ? valor : predeterminado;
}

function SelectorCampos({ selector, alCambiar }: { selector?: SelectorConfig; alCambiar: (selector: SelectorConfig) => void }) {
  const actual = selector ?? { estrategia: "css", valor: "" };
  return (
    <div className="selector-grid">
      <label>
        Estrategia
        <select value={actual.estrategia ?? "css"} onChange={(evento) => alCambiar({ ...actual, estrategia: evento.target.value })}>
          {estrategiasSelector.map(([valor, etiqueta]) => <option key={valor} value={valor}>{etiqueta}</option>)}
        </select>
      </label>
      <label>
        Selector
        <input value={actual.valor ?? ""} onChange={(evento) => alCambiar({ ...actual, valor: evento.target.value })} placeholder="correo, main h1, button[type='submit']" />
      </label>
    </div>
  );
}

export function ConstructorPruebas() {
  const [proyectos, definirProyectos] = useState<Proyecto[]>([]);
  const [secretos, definirSecretos] = useState<Secreto[]>([]);
  const [casos, definirCasos] = useState<CasoPrueba[]>([]);
  const [proyectoId, definirProyectoId] = useState("");
  const [nombre, definirNombre] = useState("Inicio de sesión con fallo conocido");
  const [requiereRevisionHumana, definirRequiereRevisionHumana] = useState(false);
  const [pasos, definirPasos] = useState<PasoCasoPrueba[]>([crearPaso(1)]);
  const [pasosColapsados, definirPasosColapsados] = useState<Set<number>>(new Set());
  const avisos = useAvisos();

  useEffect(() => {
    solicitar<RespuestaLista<Proyecto>>("/api/proyectos").then((respuesta) => {
      definirProyectos(respuesta.elementos);
      definirProyectoId(respuesta.elementos[0]?.id ?? "");
    });
    solicitar<RespuestaLista<CasoPrueba>>("/api/casos-prueba").then((respuesta) => definirCasos(respuesta.elementos));
  }, []);

  useEffect(() => {
    if (!proyectoId) {
      definirSecretos([]);
      return;
    }
    solicitar<RespuestaLista<Secreto>>(`/api/proyectos/${proyectoId}/secretos`)
      .then((respuesta) => definirSecretos(respuesta.elementos))
      .catch(() => definirSecretos([]));
  }, [proyectoId]);

  const secretosDelProyecto = useMemo(() => new Set(secretos.map((secreto) => secreto.nombre)), [secretos]);

  function actualizarPaso(indice: number, actualizacion: Partial<PasoCasoPrueba>) {
    definirPasos((actuales) => actuales.map((paso, posicion) => posicion === indice ? { ...paso, ...actualizacion } : paso));
  }

  function actualizarConfiguracion(indice: number, clave: string, valor: unknown) {
    definirPasos((actuales) => actuales.map((paso, posicion) => {
      if (posicion !== indice) return paso;
      return { ...paso, configuracion: { ...(paso.configuracion as ConfiguracionPaso), [clave]: valor } };
    }));
  }

  function actualizarSelector(indice: number, selector: SelectorConfig) {
    actualizarConfiguracion(indice, "selector", selector);
  }

  function cambiarTipo(indice: number, tipo: PasoCasoPrueba["tipo"]) {
    actualizarPaso(indice, { tipo, nombre: nombreInicial(tipo), configuracion: configuracionInicial(tipo) });
  }

  function agregarPaso() {
    definirPasos((actuales) => [...actuales, crearPaso(actuales.length + 1, "validar_texto")]);
  }

  function duplicarPaso(indice: number) {
    definirPasos((actuales) => {
      const paso = actuales[indice];
      const copia = { ...paso, id: undefined, nombre: `${paso.nombre} copia`, configuracion: { ...paso.configuracion } };
      const siguientes = [...actuales.slice(0, indice + 1), copia, ...actuales.slice(indice + 1)];
      return normalizarOrden(siguientes);
    });
  }

  function quitarPaso(indice: number) {
    definirPasos((actuales) => normalizarOrden(actuales.filter((_, posicion) => posicion !== indice)));
  }

  function moverPaso(indice: number, direccion: -1 | 1) {
    definirPasos((actuales) => {
      const destino = indice + direccion;
      if (destino < 0 || destino >= actuales.length) return actuales;
      const copia = [...actuales];
      [copia[indice], copia[destino]] = [copia[destino], copia[indice]];
      return normalizarOrden(copia);
    });
  }

  function alternarColapso(orden: number) {
    definirPasosColapsados((actuales) => {
      const siguientes = new Set(actuales);
      if (siguientes.has(orden)) {
        siguientes.delete(orden);
      } else {
        siguientes.add(orden);
      }
      return siguientes;
    });
  }

  function resumenPaso(paso: PasoCasoPrueba) {
    const configuracion = paso.configuracion as ConfiguracionPaso;
    const selector = configuracion.selector?.valor;
    const destino = texto(configuracion.ruta_o_url || configuracion.ruta || configuracion.url || configuracion.texto_esperado || configuracion.url_esperada || selector);
    return `Paso ${paso.orden} · ${nombreInicial(paso.tipo)}${destino ? ` · ${destino}` : ""}`;
  }

  function cambiarOrigenValor(indice: number, origen: string) {
    definirPasos((actuales) => actuales.map((paso, posicion) => {
      if (posicion !== indice) return paso;
      const configuracion: ConfiguracionPaso = { ...(paso.configuracion as ConfiguracionPaso), origen_valor: origen };
      if (origen === "secreto") {
        delete configuracion.texto;
        configuracion.secreto = secretos[0]?.nombre ?? "";
      } else {
        delete configuracion.secreto;
        configuracion.texto = "";
      }
      return { ...paso, configuracion };
    }));
  }

  function configuracionParaGuardar(paso: PasoCasoPrueba): ConfiguracionPaso {
    const configuracion = { ...(paso.configuracion as ConfiguracionPaso) };
    delete configuracion.origen_valor;
    delete configuracion.usar_selector;
    if (paso.tipo === "presionar_tecla" && !(paso.configuracion as ConfiguracionPaso).usar_selector) {
      delete configuracion.selector;
    }
    if (paso.tipo === "scroll" && configuracion.modalidad !== "hasta_elemento") {
      delete configuracion.selector;
    }
    if (paso.tipo === "navegar") {
      const destino = texto(configuracion.ruta_o_url);
      delete configuracion.ruta_o_url;
      if (destino.startsWith("http://") || destino.startsWith("https://")) {
        configuracion.url = destino;
        delete configuracion.ruta;
      } else if (destino) {
        configuracion.ruta = destino;
        delete configuracion.url;
      }
    }
    return configuracion;
  }

  function validarPaso(paso: PasoCasoPrueba) {
    const configuracion = paso.configuracion as ConfiguracionPaso;
    if (!paso.nombre.trim()) return "Todos los pasos necesitan nombre.";
    if (tiposConSelector.has(paso.tipo)) {
      if (!configuracion.selector?.estrategia || !configuracion.selector.valor?.trim()) return `El paso ${paso.orden} requiere selector.`;
    }
    if (paso.tipo === "navegar" && !texto(configuracion.ruta_o_url || configuracion.ruta || configuracion.url).trim()) return "El paso navegar requiere ruta o URL.";
    if (paso.tipo === "escribir") {
      if (configuracion.origen_valor === "secreto") {
        if (!texto(configuracion.secreto).trim()) return "Seleccione un secreto para escribir.";
        if (!secretosDelProyecto.has(texto(configuracion.secreto))) return "El secreto seleccionado no pertenece al proyecto.";
      } else if (!("texto" in configuracion) || !texto(configuracion.texto).trim()) {
        return "Ingrese el texto del paso escribir.";
      }
    }
    if (["esperar_texto", "validar_texto", "validar_texto_alerta"].includes(paso.tipo) && !("texto_esperado" in configuracion)) return "Complete el texto esperado.";
    if (paso.tipo === "validar_atributo" && (!texto(configuracion.atributo).trim() || !("valor_esperado" in configuracion))) return "Complete atributo y valor esperado.";
    if (paso.tipo === "validar_url" && !texto(configuracion.url_esperada).trim()) return "Complete URL o fragmento esperado.";
    if (paso.tipo === "validar_titulo" && !("titulo_esperado" in configuracion)) return "Complete el título esperado.";
    if (paso.tipo === "esperar_url" && !texto(configuracion.texto_url).trim()) return "Complete el texto de URL esperado.";
    return "";
  }

  async function guardarCaso() {
    if (!proyectoId) {
      avisos.advertencia("Seleccione un proyecto.");
      return;
    }
    if (!nombre.trim()) {
      avisos.advertencia("Ingrese el nombre del caso.");
      return;
    }
    if (pasos.length === 0) {
      avisos.advertencia("Agregue al menos un paso.");
      return;
    }
    for (const paso of pasos) {
      const error = validarPaso(paso);
      if (error) {
        avisos.advertencia(error);
        return;
      }
    }
    const pasosNormalizados = normalizarOrden(pasos).map((paso) => ({ ...paso, configuracion: configuracionParaGuardar(paso) }));
    const caso = await solicitar<CasoPrueba>("/api/casos-prueba", {
      method: "POST",
      body: JSON.stringify({ proyecto_id: proyectoId, nombre, prioridad: "alta", requiere_revision_humana: requiereRevisionHumana, pasos: pasosNormalizados })
    });
    definirCasos((actuales) => [caso, ...actuales]);
    avisos.exito("Caso guardado y listo para usarse en pipelines.");
  }

  function campoTexto(indice: number, clave: string, etiqueta: string, placeholder = "") {
    const configuracion = pasos[indice].configuracion as ConfiguracionPaso;
    return (
      <label>
        {etiqueta}
        <input value={texto(configuracion[clave])} onChange={(evento) => actualizarConfiguracion(indice, clave, evento.target.value)} placeholder={placeholder} />
      </label>
    );
  }

  function campoNumero(indice: number, clave: string, etiqueta: string, minimo = 0) {
    const configuracion = pasos[indice].configuracion as ConfiguracionPaso;
    return (
      <label>
        {etiqueta}
        <input type="number" min={minimo} value={numero(configuracion[clave], minimo)} onChange={(evento) => actualizarConfiguracion(indice, clave, Number(evento.target.value))} />
      </label>
    );
  }

  function campoComparacion(indice: number) {
    const configuracion = pasos[indice].configuracion as ConfiguracionPaso;
    return (
      <label>
        Comparación
        <select value={texto(configuracion.comparacion) || "contiene"} onChange={(evento) => actualizarConfiguracion(indice, "comparacion", evento.target.value)}>
          <option value="contiene">Contiene</option>
          <option value="igual">Igual</option>
        </select>
      </label>
    );
  }

  function camposConfiguracion(paso: PasoCasoPrueba, indice: number) {
    const configuracion = paso.configuracion as ConfiguracionPaso;
    return (
      <div className="paso-configuracion">
        {tiposConSelector.has(paso.tipo) && <SelectorCampos selector={configuracion.selector} alCambiar={(selector) => actualizarSelector(indice, selector)} />}
        {paso.tipo === "navegar" && campoTexto(indice, "ruta_o_url", "Ruta o URL", "/login")}
        {paso.tipo === "escribir" && (
          <>
            <label>
              Origen del valor
              <select value={texto(configuracion.origen_valor) || "texto"} onChange={(evento) => cambiarOrigenValor(indice, evento.target.value)}>
                <option value="texto">Texto</option>
                <option value="secreto">Secreto</option>
              </select>
            </label>
            {(texto(configuracion.origen_valor) || "texto") === "secreto" ? (
              <label>
                Secreto
                <select value={texto(configuracion.secreto)} onChange={(evento) => actualizarConfiguracion(indice, "secreto", evento.target.value)}>
                  <option value="">Seleccione secreto</option>
                  {secretos.map((secreto) => <option key={secreto.id} value={secreto.nombre}>{secreto.nombre}</option>)}
                </select>
              </label>
            ) : campoTexto(indice, "texto", "Texto", "demo@example.com")}
          </>
        )}
        {paso.tipo === "seleccionar_opcion" && (
          <>
            <label>
              Método de selección
              <select value={texto(configuracion.metodo) || "valor"} onChange={(evento) => actualizarConfiguracion(indice, "metodo", evento.target.value)}>
                <option value="valor">Valor</option>
                <option value="texto_visible">Texto visible</option>
                <option value="indice">Índice</option>
              </select>
            </label>
            {campoTexto(indice, "valor", "Valor de selección", "uno")}
          </>
        )}
        {paso.tipo === "presionar_tecla" && (
          <>
            <label className="checkbox-linea">
              <input type="checkbox" checked={Boolean(configuracion.usar_selector)} onChange={(evento: ChangeEvent<HTMLInputElement>) => actualizarConfiguracion(indice, "usar_selector", evento.target.checked)} />
              Enviar a un elemento específico
            </label>
            {Boolean(configuracion.usar_selector) && <SelectorCampos selector={configuracion.selector} alCambiar={(selector) => actualizarSelector(indice, selector)} />}
            <label>
              Tecla
              <select value={texto(configuracion.tecla) || "ENTER"} onChange={(evento) => actualizarConfiguracion(indice, "tecla", evento.target.value)}>
                {teclasPermitidas.map((tecla) => <option key={tecla} value={tecla}>{tecla}</option>)}
              </select>
            </label>
          </>
        )}
        {paso.tipo === "scroll" && (
          <>
            <label>
              Modalidad
              <select value={texto(configuracion.modalidad) || "abajo"} onChange={(evento) => actualizarConfiguracion(indice, "modalidad", evento.target.value)}>
                <option value="abajo">Abajo</option>
                <option value="arriba">Arriba</option>
                <option value="hasta_elemento">Hasta elemento</option>
              </select>
            </label>
            {configuracion.modalidad === "hasta_elemento" && <SelectorCampos selector={configuracion.selector} alCambiar={(selector) => actualizarSelector(indice, selector)} />}
          </>
        )}
        {paso.tipo === "esperar_elemento" && (
          <>
            <label>
              Condición
              <select value={texto(configuracion.condicion) || "visible"} onChange={(evento) => actualizarConfiguracion(indice, "condicion", evento.target.value)}>
                <option value="presente">Presente</option>
                <option value="visible">Visible</option>
                <option value="clickable">Clickeable</option>
              </select>
            </label>
            {campoNumero(indice, "timeout_segundos", "Timeout segundos", 1)}
          </>
        )}
        {paso.tipo === "esperar_texto" && (
          <>
            {campoTexto(indice, "texto_esperado", "Texto esperado")}
            {campoNumero(indice, "timeout_segundos", "Timeout segundos", 1)}
          </>
        )}
        {paso.tipo === "esperar_url" && (
          <>
            {campoTexto(indice, "texto_url", "Texto de URL esperado", "/demo-objetivo")}
            {campoComparacion(indice)}
            {campoNumero(indice, "timeout_segundos", "Timeout segundos", 1)}
          </>
        )}
        {paso.tipo === "validar_texto" && (
          <>
            {campoTexto(indice, "texto_esperado", "Texto esperado", "Panel principal")}
            {campoComparacion(indice)}
          </>
        )}
        {paso.tipo === "validar_atributo" && (
          <>
            {campoTexto(indice, "atributo", "Atributo", "data-estado")}
            {campoTexto(indice, "valor_esperado", "Valor esperado", "listo")}
            {campoComparacion(indice)}
          </>
        )}
        {paso.tipo === "validar_url" && (
          <>
            {campoTexto(indice, "url_esperada", "URL o fragmento esperado", "/componentes")}
            {campoComparacion(indice)}
          </>
        )}
        {paso.tipo === "validar_titulo" && (
          <>
            {campoTexto(indice, "titulo_esperado", "Título esperado", "Componentes Demo")}
            {campoComparacion(indice)}
          </>
        )}
        {paso.tipo === "validar_texto_alerta" && (
          <>
            {campoTexto(indice, "texto_esperado", "Texto esperado", "Alerta de prueba")}
            {campoComparacion(indice)}
          </>
        )}
        {paso.tipo === "cambiar_a_pestana" && campoNumero(indice, "indice", "Índice", 0)}
        {paso.tipo === "capturar_evidencia" && campoTexto(indice, "nombre", "Nombre de evidencia", "captura_manual")}
        <label className="checkbox-linea">
          <input type="checkbox" checked={Boolean(paso.continuar_si_falla)} onChange={(evento) => actualizarPaso(indice, { continuar_si_falla: evento.target.checked })} />
          Continuar si falla
        </label>
      </div>
    );
  }

  return (
    <MarcoModulo titulo="Constructor de pruebas" descripcion="Agregue pasos Selenium permitidos sin escribir código.">
      <section className="formulario">
        <label>Proyecto<select value={proyectoId} onChange={(evento) => definirProyectoId(evento.target.value)}>{proyectos.map((proyecto) => <option key={proyecto.id} value={proyecto.id}>{proyecto.nombre}</option>)}</select></label>
        <label>Nombre del caso<input value={nombre} onChange={(evento) => definirNombre(evento.target.value)} /></label>
        <label className="checkbox-linea">
          <input type="checkbox" checked={requiereRevisionHumana} onChange={(evento) => definirRequiereRevisionHumana(evento.target.checked)} />
          Requiere revisión humana
        </label>
        <div className="pasos">
          {pasos.map((paso, indice) => (
            <article className="paso" key={`${paso.orden}-${indice}`}>
              <div className="paso-cabecera">
                <strong>{paso.orden}</strong>
                <div className="paso-campos-base">
                  <label>Nombre<input value={paso.nombre} onChange={(evento) => actualizarPaso(indice, { nombre: evento.target.value })} /></label>
                  <label>
                    Acción
                    <select value={paso.tipo} onChange={(evento) => cambiarTipo(indice, evento.target.value as PasoCasoPrueba["tipo"])}>
                      {acciones.map((grupo) => (
                        <optgroup key={grupo.categoria} label={grupo.categoria}>
                          {grupo.opciones.map((opcion) => <option key={opcion.valor} value={opcion.valor}>{opcion.etiqueta}</option>)}
                        </optgroup>
                      ))}
                    </select>
                  </label>
                </div>
                <div className="paso-acciones">
                  <button type="button" className="boton-icono" onClick={() => alternarColapso(paso.orden)} aria-label="Colapsar o expandir paso">{pasosColapsados.has(paso.orden) ? <ChevronRight size={16} /> : <ChevronDown size={16} />}</button>
                  <button type="button" className="boton-icono" onClick={() => duplicarPaso(indice)} aria-label="Duplicar paso"><Copy size={16} /></button>
                  <button type="button" className="boton-icono" onClick={() => moverPaso(indice, -1)} disabled={indice === 0} aria-label="Subir paso"><ArrowUp size={16} /></button>
                  <button type="button" className="boton-icono" onClick={() => moverPaso(indice, 1)} disabled={indice === pasos.length - 1} aria-label="Bajar paso"><ArrowDown size={16} /></button>
                  <button type="button" className="boton-icono" onClick={() => quitarPaso(indice)} aria-label="Quitar paso"><Trash2 size={16} /></button>
                </div>
              </div>
              {pasosColapsados.has(paso.orden) ? <p className="paso-resumen">{resumenPaso(paso)}</p> : camposConfiguracion(paso, indice)}
            </article>
          ))}
        </div>
        <div className="botones-linea">
          <button type="button" className="secundario" onClick={agregarPaso}><Plus size={16} /> Agregar paso</button>
          <button type="button" onClick={() => guardarCaso().catch((error: Error) => avisos.error(error.message))}>Guardar caso</button>
        </div>
      </section>
      <section className="tabla-panel">
        <table><thead><tr><th>Caso</th><th>Prioridad</th><th>Revisión</th><th>Pasos</th></tr></thead><tbody>{casos.map((caso) => <tr key={caso.id}><td>{caso.nombre}</td><td>{caso.prioridad}</td><td>{caso.requiere_revision_humana ? "Humana" : "Automática"}</td><td>{caso.pasos.length}</td></tr>)}</tbody></table>
      </section>
    </MarcoModulo>
  );
}
