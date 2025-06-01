from MinMax.MinMaxAco import MinMaxACO
from MinMax.MinMaxGraph import MinMaxGraph 
from utils.generate_graph_components import generar_nodos, generar_aristas, construir_mapeo_paciente_info
from utils.plot_gantt_solution import plot_gantt_chart

import json
import os
from collections import defaultdict
from datetime import datetime, timedelta, time # time es necesario para datetime.strptime(...).time()
from typing import List

def get_configuration(config_path='/app/src/MinMax/config.json'): # Ruta al config de MinMax
    try:
        with open(config_path, 'r') as file:
            config = json.load(file)
            # Verificar claves principales, incluyendo num_dias_planificacion
            expected_keys = ["tipos_estudio", "consultas", "hora_inicio", "hora_fin", 
                             "intervalo_consultas_minutos", "medicos", "num_dias_planificacion"]
            if not all(key in config for key in expected_keys):
                missing_keys = [key for key in expected_keys if key not in config]
                print(f"Error: Faltan claves en la configuración ({config_path}): {', '.join(missing_keys)}. Esperadas: {', '.join(expected_keys)}.")
                return None

            # Validar tipo de intervalo_consultas_minutos
            if not isinstance(config["intervalo_consultas_minutos"], int) or config["intervalo_consultas_minutos"] <= 0:
                print("Error: 'intervalo_consultas_minutos' debe ser un entero positivo.")
                return None
            
            # Validar num_dias_planificacion
            if not isinstance(config["num_dias_planificacion"], int) or config["num_dias_planificacion"] <= 0:
                print("Error: 'num_dias_planificacion' debe ser un entero positivo.")
                return None

            # Validar formato de horas
            try:
                datetime.strptime(config["hora_inicio"], "%H:%M")
                datetime.strptime(config["hora_fin"], "%H:%M")
            except ValueError:
                print("Error: 'hora_inicio' o 'hora_fin' tienen formato incorrecto. Usar HH:MM.")
                return None
            
            # Verificar estructura de estudios
            for estudio in config["tipos_estudio"]:
                if not all(k in estudio for k in ["nombre_estudio", "pacientes", "fases", "orden_fases"]):
                    print(f"Error: Estructura incorrecta en estudio {estudio.get('nombre_estudio', 'DESCONOCIDO')}. Se esperan: nombre_estudio, pacientes, fases, orden_fases.")
                    return None
                if "fases_duration" in estudio: # Mantener advertencia si aún es relevante
                    print(f"Advertencia: 'fases_duration' en estudio {estudio.get('nombre_estudio', 'DESCONOCIDO')} ya no se utiliza. Se usará el 'intervalo_consultas_minutos' global.")
            return config
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo de configuración en {config_path}")
        return None
    except json.JSONDecodeError:
        print(f"Error: El archivo de configuración {config_path} no es un JSON válido.")
        return None
    except Exception as e:
        print(f"Error inesperado al cargar configuración desde {config_path}: {e}")
        return None

def generar_horas_disponibles(hora_inicio_str: str, hora_fin_str: str, intervalo_minutos: int) -> List[str]:
    """Genera una lista de strings de tiempo ("HH:MM") para un día tipo."""
    horas = []
    try:
        start_time_obj = datetime.strptime(hora_inicio_str, "%H:%M").time()
        end_time_obj = datetime.strptime(hora_fin_str, "%H:%M").time()
    except ValueError:
        print("Error: Formato de hora_inicio o hora_fin inválido en generar_horas_disponibles. Use HH:MM.")
        return []

    if intervalo_minutos <= 0:
        print("Error: intervalo_consultas_minutos debe ser positivo en generar_horas_disponibles.")
        return []

    current_dt = datetime.combine(datetime.today(), start_time_obj)
    end_datetime_limit = datetime.combine(datetime.today(), end_time_obj)

    while current_dt < end_datetime_limit:
        horas.append(current_dt.strftime("%H:%M"))
        current_dt += timedelta(minutes=intervalo_minutos)
    return horas

if __name__ == "__main__":
    # Especificar la ruta al config.json de MinMax
    config_file_path_minmax = '/app/src/MinMax/config.json' 
    config_data = get_configuration(config_file_path_minmax)

    if config_data is None:
        print("No se pudo cargar la configuración para MinMax.")
        exit(1)

    map_paciente_info = construir_mapeo_paciente_info(config_data['tipos_estudio'])
    num_dias_planificacion = config_data['num_dias_planificacion'] # Cargar desde el config

    horas_disponibles_un_dia = generar_horas_disponibles(
        config_data['hora_inicio'],
        config_data['hora_fin'],
        config_data['intervalo_consultas_minutos']
    )

    if not horas_disponibles_un_dia:
        print("Error: No se pudieron generar las horas disponibles para un día.")
        exit(1)
    
    print(f"Horas disponibles generadas (por día tipo): {horas_disponibles_un_dia}")
    print(f"Número de días para planificación: {num_dias_planificacion}")

    # Generar componentes del grafo, pasando num_dias_planificacion
    # Asumiendo que generar_nodos y generar_aristas están en utils y adaptados
    nodos = generar_nodos(config_data, horas_disponibles_un_dia, num_dias_planificacion)
    if not nodos:
        print("Error generando nodos. Verifique la configuración y las funciones de generación.")
        exit(1)
        
    aristas = generar_aristas(nodos, map_paciente_info,
                              duracion_consulta_minutos=config_data['intervalo_consultas_minutos'], 
                              horas_disponibles_str_list=horas_disponibles_un_dia)
    
    # Instanciar MinMaxGraph
    min_max_graph = MinMaxGraph(
        nodes=nodos,
        edges=aristas,
        pheromone_max=10.0,  # Ajusta estos valores según necesites
        pheromone_min=0.1,
        # initial_pheromone (opcional):, por defecto será pheromone_max
    )
    
    # Instanciar y configurar MinMaxACO
    aco_minmax = MinMaxACO(
        graph=min_max_graph, # Pasar la instancia de MinMaxGraph
        config_data=config_data,
        horas_disponibles=horas_disponibles_un_dia, # Horas de un día tipo
        num_dias_planificacion=num_dias_planificacion, # Pasar el número de días
        n_ants=20,          # Ajusta parámetros de ACO
        iterations=100, 
        alpha=1.0, 
        beta=3.0, 
        rho=0.05, # Tasa de evaporación más común para MinMax
        Q=100.0   # Ajusta Q
    )
    
    print("Ejecutando MinMaxACO...")
    best_solution, best_cost = aco_minmax.run()
    aco_minmax.plot_convergence() # Llama al método de convergencia de MinMaxACO
    
    
    if best_solution:
        asignaciones_por_paciente = defaultdict(list)
        for asignacion_tuple in best_solution: # Agrupa asignaciones por paciente
            paciente = asignacion_tuple[0]
            asignaciones_por_paciente[paciente].append(asignacion_tuple)
        
        intervalo_global_min = config_data['intervalo_consultas_minutos']

        print("\n--- Mejor Solución Encontrada (MinMaxACO) ---")
        for paciente_id in sorted(asignaciones_por_paciente.keys()):
            asignaciones_paciente = asignaciones_por_paciente[paciente_id]
            print(f"Paciente: {paciente_id}")
            
            info_estudio_paciente = aco_minmax.paciente_to_estudio.get(paciente_id)
            if info_estudio_paciente:
                print(f"  Estudio: {info_estudio_paciente['nombre_estudio']}")
                
                # Ordena asignaciones por orden de fase, día y hora
                asignaciones_ordenadas = sorted(
                    asignaciones_paciente, 
                    key=lambda asign_tuple: (
                        info_estudio_paciente['orden_fases'].get(asign_tuple[5], float('inf')),
                        asign_tuple[2],
                        datetime.strptime(asign_tuple[3], "%H:%M").time()
                    )
                )
                
                for asign_tuple_ordenada in asignaciones_ordenadas:
                    _, consulta, dia_idx, hora_str, medico, fase = asign_tuple_ordenada
                    orden = info_estudio_paciente['orden_fases'].get(fase, "N/A")
                    duracion = intervalo_global_min 
                    print(f"  Día {dia_idx + 1}, Fase {orden}. {fase} - {hora_str} ({duracion}min) - Consulta: {consulta} - Médico: {medico}")
            else:
                # Si no se encuentra información del estudio para el paciente
                print(f"  Advertencia: Información de estudio no encontrada para el paciente {paciente_id} en aco_minmax.paciente_to_estudio.")
        
        print(f"\nCosto total de la mejor solución (MinMaxACO): {best_cost:.2f}")
        if aco_minmax.execution_time is not None:
            print(f"Tiempo de ejecución (MinMaxACO): {aco_minmax.execution_time:.2f}s")

        # Gráfico de Gantt combinado para todos los pacientes
        if plot_gantt_chart:
            print("\nGenerando gráfico de línea de tiempo combinado (MinMaxACO)...")
            try:
                fases_duration_para_plot = {}
                all_configured_phase_names = set()
                for estudio_cfg in config_data['tipos_estudio']:
                    all_configured_phase_names.update(estudio_cfg['fases'])
                for phase_name in all_configured_phase_names:
                    fases_duration_para_plot[phase_name] = intervalo_global_min
                
                plot_start_hour_config = datetime.strptime(config_data['hora_inicio'], "%H:%M").hour
                plot_end_hour_config = datetime.strptime(config_data['hora_fin'], "%H:%M").hour

                plot_output_dir = "/app/plots/"
                os.makedirs(plot_output_dir, exist_ok=True)
                combined_plot_filepath = os.path.join(plot_output_dir, "timeline_todos_pacientes_MinMaxACO.png")
                
                plot_gantt_chart(
                    best_solution=best_solution, 
                    fases_duration_map=fases_duration_para_plot,
                    map_paciente_info=map_paciente_info, 
                    output_filepath=combined_plot_filepath,
                    num_dias_planificacion=num_dias_planificacion,
                    configured_start_hour=plot_start_hour_config,
                    configured_end_hour=plot_end_hour_config 
                )
            except Exception as e:
                print(f"Error generando el gráfico de línea de tiempo combinado (MinMaxACO): {e}")
                import traceback
                traceback.print_exc()
    else:
        print("\nNo se encontró ninguna solución válida con MinMaxACO.")
        if aco_minmax.execution_time is not None:
            print(f"Tiempo de ejecución (MinMaxACO): {aco_minmax.execution_time:.2f}s")