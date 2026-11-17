# Sistema Integral de Calidad Web

**Trabajo Profesional de Graduación — Universidad del Valle de Guatemala**

**Título:** Diseño e implementación de un sistema integral de automatización de pruebas funcionales y monitoreo de salud en sistemas web.

**Autor:** Mauricio Julio Rodrigo Lemus Guzmán\
**Carné:** 22461\
**Carrera:** Ingeniería en Ciencia de la Computación y Tecnologías de la Información\
**Facultad:** Ingeniería\
**Asesor:** Mgtr. Jorge Andrés Yass Coy\
**Año:** 2026

---

## 1. Descripción del proyecto

El proyecto consiste en el diseño e implementación de una plataforma web orientada al aseguramiento de la calidad del software, que integra pruebas funcionales automatizadas, monitoreo básico de salud, pipelines de ejecución, almacenamiento histórico de resultados, evidencias y notificaciones automáticas.

Su propósito es facilitar la detección, trazabilidad y análisis de fallos en sistemas web, centralizando información que tradicionalmente se encuentra distribuida entre distintas herramientas y procesos.

La plataforma permite administrar proyectos y entornos, configurar pruebas automatizadas con Selenium, ejecutar verificaciones de disponibilidad, organizar ejecuciones mediante pipelines y consultar resultados desde una interfaz web.

El sistema fue desarrollado y evaluado dentro de un entorno académico controlado, utilizando sistemas web de prueba y escenarios de evaluación definidos.

## 2. Objetivo general

Evaluar en qué medida un sistema integral de automatización de pruebas funcionales y monitoreo básico de salud, ejecutado mediante pipelines y gestionado desde una plataforma web, contribuye a la detección, trazabilidad y análisis de fallos en sistemas web empresariales, en comparación con enfoques tradicionales no integrados.

## 3. Funcionalidades principales

### Automatización de pruebas funcionales

- Creación y administración de casos de prueba.
- Ejecución automatizada mediante Selenium WebDriver.
- Automatización de navegación, formularios, clics y validaciones.
- Importación y exportación de configuraciones YAML.
- Registro de resultados individuales por paso.
- Generación y almacenamiento de evidencias.

### Monitoreo de salud

- Verificación de disponibilidad HTTP.
- Monitoreo de endpoints y servicios API.
- Comprobaciones de conectividad TCP.
- Registro de estados y tiempos de respuesta.
- Consulta histórica de verificaciones.

### Pipelines de ejecución

- Organización de pruebas y monitores en flujos de ejecución.
- Ejecución controlada de procesos.
- Registro de estados y resultados.
- Programación de tareas mediante un componente independiente.
- Consulta de ejecuciones y sus evidencias.

### Trazabilidad y resultados

- Almacenamiento estructurado de resultados.
- Consulta del historial de ejecuciones.
- Asociación de capturas y registros técnicos.
- Visualización de métricas descriptivas.
- Seguimiento de condiciones de fallo.

### Alertas y notificaciones

- Identificación de condiciones configuradas de fallo.
- Generación de alertas.
- Notificaciones mediante correo o servicios de mensajería.
- Integración con webhooks, incluyendo Discord.
- Registro de eventos y estados de notificación.

### Administración

- Autenticación de usuarios.
- Gestión de roles y permisos.
- Administración de proyectos y entornos.
- Configuración de los componentes del sistema.
- Protección de credenciales y secretos.

## 4. Arquitectura tecnológica

El sistema utiliza una arquitectura web compuesta por:

| Componente | Tecnología | Función |
|---|---|---|
| Frontend | React, TypeScript y Vite | Interfaz de administración y consulta |
| Backend | Python y Flask | API y lógica de aplicación |
| Persistencia | SQLAlchemy | Gestión de datos |
| Base de datos | PostgreSQL / SQLite | Almacenamiento de información |
| Automatización | Selenium WebDriver | Ejecución de pruebas funcionales |
| Worker | Python | Procesamiento de ejecuciones |
| Programador | Python | Planificación de tareas |
| Configuración | YAML | Definición de elementos y ejecuciones |
| Notificaciones | Correo electrónico y webhooks | Comunicación de eventos |
| Control de versiones | Git y GitHub | Gestión del código fuente |

El sistema separa la interfaz web, la API, el procesamiento de tareas y la programación de ejecuciones.

La configuración contempla PostgreSQL como base de datos principal y SQLite para determinados entornos locales de evaluación.

## 5. Estructura del repositorio

```text
2026-22461-lemus-guzman-mauricio-julio-rodrigo/
│
├── capturas/
│   └── Imágenes del sistema
│
├── demo/
│   └── demo.mp4
│
├── docs/
│   ├── informe_final.pdf
│   └── consentimiento_firmado.pdf
│
├── src/
│   ├── .env.example
│   ├── backend/
│   │   ├── aplicacion/
│   │   ├── migraciones/
│   │   ├── pruebas/
│   │   ├── programador.py
│   │   ├── trabajador.py
│   │   ├── requirements.txt
│   │   └── wsgi.py
│   │
│   ├── frontend/
│   │   └── Código de la interfaz web
│   │
│   ├── configuraciones/
│   └── scripts/
│
├── .gitignore
└── README.md
```

La distribución de componentes dentro de `src/` corresponde al código fuente del proyecto. Los archivos de ejecución y configuración deben utilizarse según su ubicación efectiva dentro del repositorio.

## 6. Requisitos previos

Para ejecutar el sistema en un ambiente de desarrollo se requiere:

- Python 3.12 o una versión compatible.
- Node.js y npm.
- Git.
- Google Chrome o Chromium.
- Selenium WebDriver y un navegador compatible.
- PostgreSQL, cuando se utilice la configuración correspondiente.
- Dependencias de Python indicadas en `requirements.txt`.
- Dependencias del frontend indicadas en `package.json`.

## 7. Instalación

### Clonar el repositorio

```bash
git clone https://github.com/Rodlemus03/2026-22461-lemus-guzman-mauricio-julio-rodrigo.git

cd 2026-22461-lemus-guzman-mauricio-julio-rodrigo
```

### Configurar el backend en Windows

Desde PowerShell:

```powershell
cd src/backend

python -m venv .venv

.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### Configurar variables de entorno

Desde `src/backend`, copiar el archivo de ejemplo ubicado en `src/`:

```powershell
Copy-Item ..\.env.example ..\.env
```

Editar `src/.env` con los valores correspondientes al entorno local.

Las variables principales del sistema incluyen:

- `CADENA_CONEXION_POSTGRESQL`
- `CLAVE_SESION`
- `CLAVE_JWT`
- `CLAVE_CIFRADO_SECRETOS`

Deben utilizarse valores seguros y únicos.

**Importante:** no incorporar credenciales reales al repositorio ni publicar el archivo `.env`.

### Preparar la base de datos

Configurar una instancia de PostgreSQL, crear la base de datos correspondiente y establecer la cadena de conexión.

Después, desde `src/backend`, con el entorno virtual activado:

```powershell
flask --app wsgi db upgrade
```

### Crear un administrador inicial

Desde `src/backend`:

```powershell
python -m aplicacion.seguridad.crear_administrador admin@example.com "Administrador" "CAMBIAR_POR_CONTRASENA_SEGURA"
```

El correo y la contraseña mostrados son valores ilustrativos y deben reemplazarse al instalar el sistema.

## 8. Ejecución

La plataforma dispone de procesos independientes para la API, el trabajador y el programador.

### Backend

Desde `src/backend`:

```powershell
flask --app wsgi run
```

### Trabajador

En otra terminal, desde `src/backend`:

```powershell
.\.venv\Scripts\python.exe trabajador.py
```

### Programador

En otra terminal, desde `src/backend`:

```powershell
.\.venv\Scripts\python.exe programador.py
```

### Frontend

Desde `src/frontend`:

```powershell
npm install
npm run dev
```

Vite mostrará la dirección local de acceso al frontend. Habitualmente utiliza el puerto 5173, aunque puede seleccionar otro si no está disponible.

## 9. Pruebas y validación

Las pruebas automatizadas del backend utilizan pytest.

Desde `src/backend`:

```powershell
python -m pytest
```

Para verificar la compilación del frontend, ejecutar desde `src/frontend`:

```powershell
npm run build
```

Las pruebas funcionales sobre aplicaciones web requieren un navegador compatible con Selenium y un entorno de evaluación accesible.

## 10. Configuración YAML

La plataforma permite utilizar YAML para definir e intercambiar configuraciones relacionadas con:

- Proyectos.
- Entornos.
- Módulos.
- Casos de prueba.
- Monitores.
- Pipelines.
- Programaciones.

Las configuraciones exportadas no deben contener secretos reales. La base de datos conserva la información operativa del sistema.

## 11. Seguridad y consideraciones de uso

El proyecto está orientado a ambientes autorizados de desarrollo, pruebas y preproducción.

Se contemplan las siguientes consideraciones:

- Protección de credenciales y configuraciones sensibles.
- Gestión de usuarios y roles.
- Restricciones de acceso a evidencias.
- Uso de datos ficticios o anonimizados.
- Registro de acciones y eventos relevantes.
- Exclusión de secretos en archivos públicos.
- Revisión humana de resultados, fallos y notificaciones.

La plataforma no pretende sustituir sistemas empresariales completos de observabilidad, herramientas especializadas de ciberseguridad ni procesos profesionales de gestión de incidentes.

## 12. Evaluación y resultados

La plataforma se evaluó mediante escenarios de prueba controlados, revisión de registros históricos y una comparación de tiempos frente a procedimientos manuales no integrados.

Durante la evaluación se documentaron ejecuciones de pruebas funcionales, monitoreo de salud, generación de evidencias, almacenamiento de resultados y notificaciones.

La investigación permitió analizar la disponibilidad de información histórica, la trazabilidad de ejecuciones y los tiempos observados para diferentes escenarios.

Los resultados, indicadores, limitaciones y procedimientos de evaluación se encuentran documentados en el informe final del Trabajo Profesional de Graduación.

## 13. Demostración del sistema

El repositorio incluye un video demostrativo del funcionamiento de la plataforma.

**Video:** [Ver demostración](demo/demo.mp4)

La demostración presenta las funcionalidades principales del sistema, incluyendo la administración de proyectos, automatización de pruebas, monitoreo, pipelines y consulta de resultados.

## 14. Capturas de pantalla

La carpeta [`capturas/`](capturas/) contiene evidencias visuales del funcionamiento de la plataforma.

Estas imágenes muestran sus diferentes módulos, interfaces de administración, configuraciones, ejecuciones y resultados.

## 15. Documentación académica

El trabajo escrito y la documentación de entrega se encuentran en la carpeta `docs/`.

- [Informe final del Trabajo de Graduación](docs/informe_final.pdf)
- [Consentimiento de uso de fotografía y video](docs/consentimiento_firmado.pdf)

El informe final incluye el planteamiento del problema, objetivos, marco teórico, antecedentes, alcance, metodología, resultados, análisis, conclusiones, recomendaciones y anexos.

## 16. Despliegue

Para un despliegue en un ambiente administrado pueden utilizarse Gunicorn, Nginx y servicios independientes para los componentes del backend.

La arquitectura del proyecto no requiere Docker, Docker Compose ni Kubernetes.

La configuración de producción debe realizarse con controles de acceso, credenciales seguras, mecanismos apropiados de persistencia y protección de evidencias.

## 17. Autor y contexto académico

**Mauricio Julio Rodrigo Lemus Guzmán**\
Ingeniería en Ciencia de la Computación y Tecnologías de la Información\
Universidad del Valle de Guatemala\
Guatemala, 2026

**Asesor académico:** Mgtr. Jorge Andrés Yass Coy

Proyecto desarrollado como Trabajo Profesional de Graduación para optar al grado académico de Licenciado en Ingeniería en Ciencia de la Computación y Tecnologías de la Información.
