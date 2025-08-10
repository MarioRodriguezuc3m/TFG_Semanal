# 🐜 Optimización de Horarios con ACO
Este proyecto ofrece una implementación del algoritmo de **Optimización por Colonia de Hormigas (ACO)** en Python, para la planificación para múltiples días de citas en un centro que realiza estudios clínicos, inspirado en la logística de CEVAXIN. Se incluyen dos variantes del algoritmo: la versión **Estándar** y la versión **Min-Max**. 
La aplicación está diseñada para ser ejecutada tanto en un entorno de Python local o a través de la contenedores de Docker basados en una imagen de Pypy, con el objetivo de mejorar el tiempod de ejecución del programa.
A continuación se detalla como ejecutar el programa siguiendo ambos enfoques:

## 1. Ejecución Local con Python 🐍

Para ejecutar el programa se recomienda tener instalada una versión de Python igual o superior a la 3.10. En el desarrollo de este proyecto se ha usado Python 3.13.1.

Se recomienda crear un entorno virtual (venv) para instalar las dependencias y evitar conflictos con otras librerías del sistema.

### Crear y activar el entorno virtual

- En Linux/macOS (bash/zsh):

    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

- En Windows (PowerShell):

    ```powershell
    python -m venv venv
    .\venv\Scripts\Activate.ps1
    ```

### Instalar las dependencias

```bash
pip install -r requirements.txt
```

## Ejecutar el programa

Primero, se debe configurar la variable de entorno `PYTHONPATH` para que incluya la carpeta `src`:

**En Windows PowerShell:**

```powershell
$env:PYTHONPATH="src"
```

** En Linux**
```powershell
export PYTHONPATH="src"
```

Y desde la raiz del directorio se utilizan los siguientes comandos para ejecutar el programa:

```powershell
python -m MinMax.main   # Para la versión MinMax
python -m Standard.main # Para la versión Standard
```

Si se quieren customizar la localización de los archivos de configuración o la carpeta donde se almacenarán los gráficos generados, esto se puede modificar mediante las variables de entorno ACO_CONFIG_PATH,ACO_PARAMS_PATH,PLOT_DIR_PATH .
Ejemplo de comandos para realizar esta configuración:

**En Linux**
```powershell
export ACO_CONFIG_PATH="/ruta/a/config.json"
export ACO_PARAMS_PATH="/ruta/a/params_config.json"
export PLOT_DIR_PATH="/ruta/a/plots"
```

** En Windows**
```powershell
$env:ACO_CONFIG_PATH="C:\ruta\a\config.json"
$env:ACO_PARAMS_PATH="C:\ruta\a\params_config.json"
$env:PLOT_DIR_PATH="C:\ruta\a\plots"
```

## 2. Ejecución con Docker (Pypy) 🐳

Para ejecutar el programa con un contenedor de Pypy, es necesario instalar Docker en el equipo donde se desee ejecutar el programa. 

Una vez instalado, se debe compilar la imagen ejecutando el siguiente comando desde la raíz del directorio:

- **Imagen Standard:**

    ```bash
    docker build -f Dockerfile.standard -t standardaco .
    ```

- **Imagen Min-Max:**

    ```bash
    docker build -f Dockerfile.minmax -t minmaxaco .
    ```

Para ejecutar el programa, se utiliza este comando que montará un volumen en la carpeta actual desde donde se lance el comando, generando una subcarpeta `plots` con las gráficas generadas:

- **Contenedor Standard:**

    ```bash
    docker run --rm -v "$(pwd)/plots:/app/plots" -e PYTHONUNBUFFERED=1 standardaco
    ```

- **Contenedor Min-Max:**

    ```bash
    docker run --rm -v "$(pwd)/plots:/app/plots" -e PYTHONUNBUFFERED=1 minmaxaco
    ```

## 📄 Configuración

Los parametroso del algoritmo y el escenario de planificación se definen en dos archivos JSON principales, ubicados en la carpeta de cada implementación (Standard o MinMax). Es importante respetar su estructura.

⚠️ Si el programa se ejecuta con un contenedor de Pypy es importante volver a compilar la imagen antes de ejecutar el programa, ya que si no los cambios no se verán reflejados al ejecutar el contenedor.

### `params_config.json`
Define los hiperparámetros del algoritmo ACO.

```json
{
    "n_ants": 50,
    "iterations": 50,
    "alpha": 1.0,
    "beta": 4.0,
    "rho": 0.02,
    "Q": 1000.0
}
```
En el params_config.json de la versión MinMax adicionalmente habrá dos valores más que representan el valor máximo y mínimo de los niveles de feromonas que se podrán depositar en las aristas del grafo. Estos parámetros son exclusivos de esta versión del ACO.
```json
{
    "pheromone_max":10.0,
    "pheromone_min": 0.1
}
```
### `config.json`

Contiene todos los parámetros para configurar el escenario de planificación (estudios, personal, consultas, etc.).
```json
{
  "tipos_estudio": [
    {
      "nombre_estudio": "Estudio Polio",
      "pacientes": ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8"],
      "fases": ["Admision", "Historia", "Prueba_Medica", "Laboratorio", "Entrega_Resultados", "Cierre"],
      "orden_fases": { "Admision": 1, "Historia": 2, "Prueba_Medica": 3, "Laboratorio": 4, "Entrega_Resultados": 5, "Cierre": 6 }
    },
    {
      "nombre_estudio": "Estudio Diabetes",
      "pacientes": ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8"],
      "fases": ["Admision", "Historia", "Analisis_Sangre", "Revisión_Medica", "Entrega_Resultados", "Cierre"],
      "orden_fases": { "Admision": 1, "Historia": 2, "Analisis_Sangre": 3, "Revisión_Medica": 4, "Entrega_Resultados": 5, "Cierre": 6 }
    }
  ],
  "consultas": ["ConsultaA", "ConsultaB", "ConsultaC", "ConsultaD"],
  "hora_inicio": "07:00",
  "hora_fin": "22:00",
  "num_dias_planificacion":5,
  "intervalo_consultas_minutos": 60,
  "max_fases_por_dia_paciente": 3,
  "roles": ["MG", "LB", "AC"],
  "personal": { "MG": 2, "LB": 2, "AC": 2 },
  "cargos": {
    "AC": ["Admision", "Cierre"],
    "MG": ["Historia", "Prueba_Medica", "Revisión_Medica"],
    "LB": ["Laboratorio", "Entrega_Resultados", "Analisis_Sangre"]
  }
}
```
