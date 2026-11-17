export type UsuarioSesion = {
  id: string;
  nombre: string;
  correo: string;
  roles: string[];
  activo?: boolean;
  ultimo_acceso?: string;
  tour_completado?: boolean;
  creado_en?: string;
};

export type Rol = {
  id: string;
  nombre: string;
  descripcion: string;
};

export type Proyecto = {
  id: string;
  nombre: string;
  descripcion: string;
  tecnologia_referencial?: string;
  responsable?: string;
  activo: boolean;
};

export type Entorno = {
  id: string;
  proyecto_id: string;
  nombre: string;
  url_base: string;
  zona_horaria: string;
  verificar_certificado_tls: boolean;
  tiempo_espera_segundos: number;
  activo: boolean;
};

export type CasoPrueba = {
  id: string;
  proyecto_id: string;
  nombre: string;
  prioridad: string;
  requiere_revision_humana?: boolean;
  pasos: PasoCasoPrueba[];
};

export type PasoCasoPrueba = {
  id?: string;
  orden: number;
  tipo:
    | "navegar"
    | "retroceder"
    | "avanzar"
    | "recargar"
    | "escribir"
    | "limpiar_campo"
    | "hacer_clic"
    | "doble_clic"
    | "clic_derecho"
    | "mover_mouse"
    | "seleccionar_opcion"
    | "marcar_checkbox"
    | "desmarcar_checkbox"
    | "presionar_tecla"
    | "scroll"
    | "esperar_elemento"
    | "esperar_texto"
    | "esperar_url"
    | "validar_texto"
    | "validar_elemento_visible"
    | "validar_elemento_existente"
    | "validar_elemento_habilitado"
    | "validar_elemento_seleccionado"
    | "validar_atributo"
    | "validar_url"
    | "validar_titulo"
    | "aceptar_alerta"
    | "cancelar_alerta"
    | "validar_texto_alerta"
    | "cambiar_a_nueva_pestana"
    | "cambiar_a_pestana"
    | "cerrar_pestana"
    | "capturar_evidencia";
  nombre: string;
  configuracion: Record<string, unknown>;
  continuar_si_falla?: boolean;
  capturar_evidencia?: boolean;
};

export type Monitor = {
  id: string;
  proyecto_id: string;
  entorno_id?: string;
  nombre: string;
  tipo: string;
  configuracion: Record<string, unknown>;
  activo: boolean;
};

export type Secreto = {
  id: string;
  proyecto_id: string;
  entorno_id?: string;
  nombre: string;
  tipo: string;
  creado_en?: string;
  actualizado_en?: string;
};

export type Pipeline = {
  id: string;
  proyecto_id: string;
  nombre: string;
  detener_ante_fallo: boolean;
  pasos: PasoPipeline[];
};

export type PasoPipeline = {
  orden: number;
  tipo: "monitor" | "caso_prueba";
  nombre: string;
  monitor_id?: string;
  caso_prueba_id?: string;
  continuar_si_falla?: boolean;
};

export type Ejecucion = {
  id: string;
  pipeline_id: string;
  pipeline_nombre?: string;
  entorno_id: string;
  entorno_nombre?: string;
  proyecto_id?: string;
  proyecto_nombre?: string;
  origen: string;
  estado: string;
  fecha_encolado: string;
  fecha_inicio?: string;
  fecha_fin?: string;
  duracion_milisegundos?: number;
  error_tecnico?: string;
  requiere_revision_humana?: boolean;
  revision_humana?: RevisionHumana;
  resultados: ResultadoPaso[];
  evidencias?: Evidencia[];
  alertas?: Alerta[];
};

export type InformeEjecucion = {
  id: string;
  ejecucion_id: string;
  nombre_archivo: string;
  tamano_bytes: number;
  hash_sha256: string;
  generado_en: string;
  zona_horaria: string;
  version: number;
  url: string;
};

export type ResultadoPaso = {
  id: string;
  paso_caso_prueba_id?: string;
  paso_pipeline_id?: string;
  contexto?: ContextoResultado;
  tipo: string;
  estado: string;
  esperado: string;
  obtenido: string;
  mensaje: string;
  fecha_inicio?: string;
  fecha_fin?: string;
  duracion_milisegundos?: number;
  datos_tecnicos_sanitizados?: Record<string, unknown>;
  revision_humana?: RevisionHumana;
};

export type ContextoResultado = {
  paso_pipeline?: string;
  orden_pipeline?: number;
  tipo_pipeline?: string;
  caso_prueba?: string;
  paso_prueba?: string;
  orden_prueba?: number;
  accion?: string;
  selector?: Record<string, unknown>;
  monitor?: string;
};

export type RevisionHumana = {
  id: string;
  clasificacion: string;
  comentario: string;
  revisado_por: string;
  creado_en: string;
  actualizado_en: string;
};

export type Alerta = {
  id: string;
  ejecucion_id: string;
  tipo: string;
  severidad: string;
  estado_revision: string;
  clasificacion_manual: string;
  fecha_deteccion?: string;
  observacion_revision?: string;
  ejecucion?: Ejecucion;
  resultado_principal?: ResultadoPaso;
};

export type Evidencia = {
  id: string;
  ejecucion_id: string;
  resultado_paso_id?: string;
  tipo: string;
  nombre_archivo: string;
  tipo_contenido: string;
  tamano_bytes: number;
  hash_sha256: string;
  creado_en: string;
};

export type CanalNotificacion = {
  id: string;
  proyecto_id: string;
  nombre: string;
  tipo: "webhook" | "correo";
  activo: boolean;
};

export type Programacion = {
  id: string;
  pipeline_id: string;
  nombre: string;
  tipo_frecuencia: string;
  configuracion_frecuencia: Record<string, unknown>;
  zona_horaria: string;
  siguiente_ejecucion?: string;
  activo: boolean;
};

export type RespuestaLista<T> = {
  elementos: T[];
};
