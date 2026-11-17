const URL_API = import.meta.env.VITE_URL_API ?? "";

export class ErrorApi extends Error {
  codigo: string;

  constructor(codigo: string, mensaje: string) {
    super(mensaje);
    this.codigo = codigo;
  }
}

function leerCookie(nombre: string): string | undefined {
  return document.cookie
    .split(";")
    .map((parte) => parte.trim())
    .find((parte) => parte.startsWith(`${nombre}=`))
    ?.split("=")[1];
}

export async function solicitar<T>(ruta: string, opciones: RequestInit = {}): Promise<T> {
  const csrf = leerCookie("csrf_access_token");
  const encabezados = {
    "Content-Type": "application/json",
    ...(csrf ? { "X-CSRF-TOKEN": decodeURIComponent(csrf) } : {}),
    ...(opciones.headers ?? {})
  };
  const respuesta = await fetch(`${URL_API}${ruta}`, {
    ...opciones,
    credentials: "include",
    headers: encabezados
  });
  const texto = await respuesta.text();
  const cuerpo = texto ? JSON.parse(texto) : {};
  if (!respuesta.ok) {
    throw new ErrorApi(cuerpo.codigo ?? "solicitud_fallida", cuerpo.mensaje ?? "No se pudo completar la solicitud.");
  }
  return cuerpo as T;
}

export function construirUrlApi(ruta: string): string {
  return `${URL_API}${ruta}`;
}
